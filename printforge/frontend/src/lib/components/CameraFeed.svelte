<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { api } from '../api';

	type StreamMode = 'snapshot' | 'mjpeg-direct' | 'mjpeg-proxy';

	let mjpegUrl = $state('');
	let proxyUrl = $state('');
	let snapshotUrl = $state('');
	let streamMode = $state<StreamMode>('snapshot');
	let error = $state('');
	let loading = $state(true);
	let retryCount = $state(0);
	let retryTimer: ReturnType<typeof setTimeout> | null = null;
	let paused = $state(false);
	let fullscreen = $state(false);
	let containerEl: HTMLDivElement;
	let canvasEl: HTMLCanvasElement;
	let imgEl: HTMLImageElement;
	const MAX_RETRIES = 5;

	// Snapshot polling state
	let pollActive = false;
	let rafId: number | null = null;
	let fps = $state(0);
	let frameTimestamps: number[] = [];
	let fetchInFlight = false; // prevents overlapping fetches
	let abortController: AbortController | null = null;
	const FETCH_TIMEOUT = 5000; // abort hung fetches after 5s

	onMount(async () => {
		await loadCamera();
		document.addEventListener('visibilitychange', onVisibility);
		document.addEventListener('fullscreenchange', onFullscreenChange);
	});

	onDestroy(() => {
		stopPolling();
		if (retryTimer) clearTimeout(retryTimer);
		document.removeEventListener('visibilitychange', onVisibility);
		document.removeEventListener('fullscreenchange', onFullscreenChange);
	});

	function onVisibility() {
		if (document.hidden) {
			paused = true;
			stopPolling();
		} else {
			paused = false;
			if (streamMode === 'snapshot') {
				startPolling();
			} else if (error) {
				loadCamera();
			}
		}
	}

	function onFullscreenChange() {
		fullscreen = !!document.fullscreenElement;
	}

	async function loadCamera() {
		loading = true;
		error = '';
		try {
			const urls = await api.getCameraUrls();
			mjpegUrl = urls.mjpeg || '';
			proxyUrl = urls.proxy || '';
			snapshotUrl = urls.snapshot || '/api/camera/snapshot';

			// Default to snapshot polling (most reliable, lowest latency)
			streamMode = 'snapshot';
			startPolling();
			retryCount = 0;
		} catch (e) {
			error = 'Camera not available';
			loading = false;
		}
	}

	function switchMode(mode: StreamMode) {
		stopPolling();
		// Clear retry timer to prevent stale retries from interfering
		if (retryTimer) { clearTimeout(retryTimer); retryTimer = null; }
		// Clear MJPEG img src to force browser to close the stream connection
		if (imgEl) imgEl.src = '';
		streamMode = mode;
		error = '';
		loading = true;

		if (mode === 'snapshot') {
			startPolling();
		} else {
			// MJPEG modes use an <img> tag
			loading = false;
		}
	}

	// ── Snapshot polling with canvas rendering ──────────────────

	function startPolling() {
		if (pollActive) return;
		pollActive = true;
		frameTimestamps = [];
		fetchInFlight = false;
		// Kick off the first fetch, then use rAF loop to draw + pipeline
		fetchFrame();
		scheduleFrame();
	}

	function stopPolling() {
		pollActive = false;
		if (rafId) {
			cancelAnimationFrame(rafId);
			rafId = null;
		}
		// Abort any in-flight fetch so it doesn't hang forever
		if (abortController) {
			abortController.abort();
			abortController = null;
		}
	}

	// Detect createImageBitmap support once (older Safari/iOS may lack it)
	const hasImageBitmap = typeof createImageBitmap === 'function';

	/** Convert blob to a drawable image source (off-thread if possible). */
	function blobToDrawable(blob: Blob): Promise<ImageBitmap | HTMLImageElement> {
		if (hasImageBitmap) return createImageBitmap(blob);
		return new Promise((resolve, reject) => {
			const img = new Image();
			const objUrl = URL.createObjectURL(blob);
			img.onload = () => { URL.revokeObjectURL(objUrl); resolve(img); };
			img.onerror = () => { URL.revokeObjectURL(objUrl); reject(new Error('decode')); };
			img.src = objUrl;
		});
	}

	// Auth headers cached once
	function getAuthHeaders(): Record<string, string> {
		const headers: Record<string, string> = {};
		const apiKey = typeof localStorage !== 'undefined' ? localStorage.getItem('printforge:apiKey') : null;
		if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`;
		return headers;
	}
	const authHeaders = getAuthHeaders();

	// Pending drawable ready to be painted on next rAF
	let pendingDrawable: (ImageBitmap | HTMLImageElement) | null = null;

	/** Fetch a snapshot and decode it off-thread. Sets pendingDrawable when ready. */
	function fetchFrame() {
		if (!pollActive || paused || fetchInFlight) return;
		fetchInFlight = true;

		// Abort any previous controller and create a fresh one with timeout
		if (abortController) abortController.abort();
		abortController = new AbortController();
		const timeoutId = setTimeout(() => abortController?.abort(), FETCH_TIMEOUT);

		fetch(`${snapshotUrl}?t=${Date.now()}`, { headers: authHeaders, signal: abortController.signal })
			.then(r => {
				clearTimeout(timeoutId);
				if (!r.ok) throw new Error(`HTTP ${r.status}`);
				return r.blob();
			})
			.then(blob => blobToDrawable(blob))
			.then(drawable => {
				if (!pollActive) {
					if ('close' in drawable) drawable.close();
					return;
				}
				// Dispose previous un-drawn frame if one was pending
				if (pendingDrawable && 'close' in pendingDrawable) pendingDrawable.close();
				pendingDrawable = drawable;
				fetchInFlight = false;
				retryCount = 0;

				// Immediately start fetching the NEXT frame (pipeline)
				fetchFrame();
			})
			.catch(() => {
				clearTimeout(timeoutId);
				fetchInFlight = false;
				if (!pollActive) return;
				retryCount++;
				if (retryCount >= MAX_RETRIES) {
					error = 'Camera stream unavailable';
					loading = false;
					stopPolling();
					return;
				}
				// Back off on errors, then retry
				setTimeout(fetchFrame, Math.min(1000 * retryCount, 5000));
			});
	}

	/** rAF loop — draws the latest decoded frame to canvas. */
	function scheduleFrame() {
		if (!pollActive) return;
		rafId = requestAnimationFrame(() => {
			if (!pollActive) return;

			if (pendingDrawable) {
				// Clear loading/error FIRST so Svelte renders the <canvas> into the DOM.
				// On the very first frame canvasEl won't exist yet because loading=true
				// hides the canvas — setting loading=false here lets Svelte mount it,
				// and the next rAF tick will draw.
				if (loading || error) {
					loading = false;
					error = '';
				}

				if (canvasEl) {
					const ctx = canvasEl.getContext('2d');
					if (ctx) {
						const d = pendingDrawable;
						const w = d instanceof HTMLImageElement ? d.naturalWidth : d.width;
						const h = d instanceof HTMLImageElement ? d.naturalHeight : d.height;
						if (canvasEl.width !== w || canvasEl.height !== h) {
							canvasEl.width = w;
							canvasEl.height = h;
						}
						ctx.drawImage(d, 0, 0);
					}
					if ('close' in pendingDrawable) pendingDrawable.close();
					pendingDrawable = null;

					// Track FPS
					const now = performance.now();
					frameTimestamps.push(now);
					const cutoff = now - 2000;
					frameTimestamps = frameTimestamps.filter(t => t > cutoff);
					fps = Math.round(frameTimestamps.length / 2);
				}
				// If canvasEl isn't available yet (Svelte hasn't re-rendered),
				// keep pendingDrawable — it'll be drawn on the next rAF tick.
			}

			scheduleFrame();
		});
	}

	// ── MJPEG error handling ───────────────────────────────────

	function onImgError() {
		if (streamMode === 'mjpeg-direct' && proxyUrl) {
			streamMode = 'mjpeg-proxy';
			return;
		}
		if (streamMode === 'mjpeg-proxy') {
			// Fall back to snapshot polling
			switchMode('snapshot');
			return;
		}
		error = 'Camera stream unavailable';
		scheduleRetry();
	}

	function onImgLoad() {
		loading = false;
		error = '';
		retryCount = 0;
	}

	function scheduleRetry() {
		if (retryTimer) clearTimeout(retryTimer);
		if (retryCount >= MAX_RETRIES || paused) return;
		const delay = Math.min(3000 * Math.pow(2, retryCount), 30000);
		retryCount++;
		retryTimer = setTimeout(() => loadCamera(), delay);
	}

	function manualRetry() {
		retryCount = 0;
		error = '';
		loadCamera();
	}

	async function toggleFullscreen() {
		if (!containerEl) return;
		if (!document.fullscreenElement) {
			try {
				await containerEl.requestFullscreen();
			} catch { /* fullscreen not supported */ }
		} else {
			await document.exitFullscreen();
		}
	}

	let modeLabel = $derived(
		streamMode === 'snapshot' ? `Snapshot ${fps}fps` :
		streamMode === 'mjpeg-direct' ? 'MJPEG' :
		'Proxied'
	);

	let currentMjpegSrc = $derived(
		streamMode === 'mjpeg-proxy' ? proxyUrl : mjpegUrl
	);
</script>

<div class="card h-full" bind:this={containerEl}>
	<div class="flex items-center justify-between mb-2">
		<h3 class="text-sm font-medium text-surface-400">Camera</h3>
		<div class="flex items-center gap-2">
			{#if !error && !loading}
				<span class="text-xs text-surface-600">{modeLabel}</span>
				<!-- Mode switcher -->
				<div class="flex gap-0.5 bg-surface-800 rounded-md p-0.5">
					<button
						class="px-1.5 py-0.5 text-[10px] rounded transition-colors
							   {streamMode === 'snapshot' ? 'bg-surface-700 text-surface-200' : 'text-surface-500 hover:text-surface-300'}"
						onclick={() => switchMode('snapshot')}
						title="Snapshot polling (most reliable)"
					>SNAP</button>
					<button
						class="px-1.5 py-0.5 text-[10px] rounded transition-colors
							   {streamMode.startsWith('mjpeg') ? 'bg-surface-700 text-surface-200' : 'text-surface-500 hover:text-surface-300'}"
						onclick={() => switchMode(mjpegUrl ? 'mjpeg-direct' : 'mjpeg-proxy')}
						title="MJPEG stream (higher FPS when available)"
					>MJPEG</button>
				</div>
			{/if}
			{#if !loading && !error}
				<button
					class="btn-icon p-1"
					onclick={toggleFullscreen}
					title={fullscreen ? 'Exit fullscreen' : 'Fullscreen'}
				>
					{#if fullscreen}
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
						</svg>
					{:else}
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
						</svg>
					{/if}
				</button>
			{/if}
		</div>
	</div>
	<div class="relative aspect-video bg-surface-800 rounded-lg overflow-hidden {fullscreen ? 'h-full aspect-auto' : ''}">
		{#if loading}
			<div class="absolute inset-0 flex items-center justify-center">
				<div class="animate-spin rounded-full h-8 w-8 border-2 border-surface-600 border-t-accent"></div>
			</div>
		{:else if error}
			<div class="absolute inset-0 flex items-center justify-center text-surface-500">
				<div class="text-center">
					<svg class="w-12 h-12 mx-auto mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
					</svg>
					<p class="text-sm mb-2">{error}</p>
					{#if retryCount < MAX_RETRIES}
						<p class="text-xs text-surface-600">Retrying... ({retryCount}/{MAX_RETRIES})</p>
					{:else}
						<button class="btn-secondary text-xs px-3 py-1.5 mt-1" onclick={manualRetry}>
							Retry
						</button>
					{/if}
				</div>
			</div>
		{:else if paused}
			<div class="absolute inset-0 flex items-center justify-center text-surface-500">
				<p class="text-sm">Camera paused (tab hidden)</p>
			</div>
		{:else if streamMode === 'snapshot'}
			<canvas
				bind:this={canvasEl}
				class="w-full h-full object-cover"
			></canvas>
		{:else}
			<img
				bind:this={imgEl}
				src={currentMjpegSrc}
				alt="Printer camera"
				class="w-full h-full object-cover"
				decoding="async"
				fetchpriority="high"
				onerror={onImgError}
				onload={onImgLoad}
			/>
		{/if}
	</div>
</div>
