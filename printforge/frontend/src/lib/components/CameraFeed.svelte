<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { api } from '../api';

	type StreamMode = 'snapshot' | 'mjpeg';

	let mjpegUrl = $state('');
	let snapshotUrl = $state('');
	let streamMode = $state<StreamMode>('mjpeg');
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

	// MJPEG fallback: try direct ustreamer first, then proxy
	let directMjpegUrl = '';
	let triedProxy = false;

	// Snapshot polling state
	let pollActive = false;
	let rafId: number | null = null;
	let fps = $state(0);
	let frameTimestamps: number[] = [];
	let fetchInFlight = false;
	let abortController: AbortController | null = null;
	const FETCH_TIMEOUT = 5000;

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
			if (streamMode === 'snapshot') {
				stopPolling();
			} else if (imgEl) {
				// Close the MJPEG stream connection while tab is hidden
				imgEl.src = '';
			}
		} else {
			paused = false;
			if (streamMode === 'snapshot') {
				startPolling();
			} else if (streamMode === 'mjpeg' && mjpegUrl) {
				// Reconnect MJPEG stream (it stalls when tab is hidden)
				if (imgEl) imgEl.src = mjpegUrl + '?t=' + Date.now();
			}
		}
	}

	function onFullscreenChange() {
		fullscreen = !!document.fullscreenElement;
	}

	async function loadCamera() {
		loading = true;
		error = '';
		triedProxy = false;
		try {
			const urls = await api.getCameraUrls();
			directMjpegUrl = urls.mjpeg || '';
			mjpegUrl = directMjpegUrl;
			snapshotUrl = urls.snapshot || '/api/camera/snapshot';

			// Default to MJPEG (direct ustreamer connection, highest FPS)
			streamMode = 'mjpeg';
			// Must clear loading so the <img> tag renders into the DOM —
			// onImgLoad/onImgError fire once it's mounted and the stream starts
			loading = false;
			retryCount = 0;
		} catch (e) {
			error = 'Camera not available';
			loading = false;
		}
	}

	function switchMode(mode: StreamMode) {
		stopPolling();
		if (retryTimer) { clearTimeout(retryTimer); retryTimer = null; }
		if (imgEl) imgEl.src = '';
		streamMode = mode;
		error = '';

		if (mode === 'snapshot') {
			loading = true;
			startPolling();
		} else {
			// Reset MJPEG to direct URL when manually switching back
			triedProxy = false;
			mjpegUrl = directMjpegUrl;
		}
		// MJPEG: loading stays false so <img> renders immediately
	}

	// ── Snapshot polling with canvas rendering ──────────────────

	function startPolling() {
		if (pollActive) return;
		pollActive = true;
		frameTimestamps = [];
		fetchInFlight = false;
		fetchFrame();
		scheduleFrame();
	}

	function stopPolling() {
		pollActive = false;
		if (rafId) {
			cancelAnimationFrame(rafId);
			rafId = null;
		}
		if (abortController) {
			abortController.abort();
			abortController = null;
		}
	}

	const hasImageBitmap = typeof createImageBitmap === 'function';

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

	function getAuthHeaders(): Record<string, string> {
		const headers: Record<string, string> = {};
		const apiKey = typeof localStorage !== 'undefined' ? localStorage.getItem('printforge:apiKey') : null;
		if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`;
		return headers;
	}
	let pendingDrawable: (ImageBitmap | HTMLImageElement) | null = null;

	function fetchFrame() {
		if (!pollActive || paused || fetchInFlight) return;
		fetchInFlight = true;

		// Refresh auth headers each call so API key changes take effect
		// without requiring a page reload
		const headers = getAuthHeaders();

		if (abortController) abortController.abort();
		abortController = new AbortController();
		const timeoutId = setTimeout(() => abortController?.abort(), FETCH_TIMEOUT);

		fetch(`${snapshotUrl}?t=${Date.now()}`, { headers, signal: abortController.signal })
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
				if (pendingDrawable && 'close' in pendingDrawable) pendingDrawable.close();
				pendingDrawable = drawable;
				fetchInFlight = false;
				retryCount = 0;
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
				setTimeout(fetchFrame, Math.min(1000 * retryCount, 5000));
			});
	}

	function scheduleFrame() {
		if (!pollActive) return;
		rafId = requestAnimationFrame(() => {
			if (!pollActive) return;

			if (pendingDrawable) {
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

					const now = performance.now();
					frameTimestamps.push(now);
					const cutoff = now - 2000;
					frameTimestamps = frameTimestamps.filter(t => t > cutoff);
					fps = Math.round(frameTimestamps.length / 2);
				}
			}

			scheduleFrame();
		});
	}

	// ── MJPEG event handling ──────────────────────────────────

	function onImgError() {
		if (streamMode === 'mjpeg' && !triedProxy) {
			// Direct ustreamer URL failed — try the backend proxy as fallback
			triedProxy = true;
			mjpegUrl = '/api/camera/mjpeg';
		} else {
			// Both MJPEG sources failed — fall back to snapshot polling
			switchMode('snapshot');
		}
	}

	function onImgLoad() {
		loading = false;
		error = '';
		retryCount = 0;
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
		streamMode === 'snapshot' ? `Snap ${fps}fps` : 'MJPEG'
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
							   {streamMode === 'mjpeg' ? 'bg-surface-700 text-surface-200' : 'text-surface-500 hover:text-surface-300'}"
						onclick={() => switchMode('mjpeg')}
						title="MJPEG stream (highest FPS)"
					>MJPEG</button>
					<button
						class="px-1.5 py-0.5 text-[10px] rounded transition-colors
							   {streamMode === 'snapshot' ? 'bg-surface-700 text-surface-200' : 'text-surface-500 hover:text-surface-300'}"
						onclick={() => switchMode('snapshot')}
						title="Snapshot polling (fallback)"
					>SNAP</button>
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
				src={mjpegUrl}
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
