<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { api } from '../api';

	type StreamMode = 'snapshot' | 'mjpeg-direct' | 'mjpeg-proxy';

	let mjpegUrl = $state('');
	let proxyUrl = $state('');
	let snapshotUrl = $state('');
	let snapshotDirectUrl = $state('');
	let streamMode = $state<StreamMode>('mjpeg-direct');
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

	// MJPEG load timeout — if direct doesn't produce a frame in this time, fall back
	let mjpegLoadTimer: ReturnType<typeof setTimeout> | null = null;
	const MJPEG_LOAD_TIMEOUT = 5000;

	// Snapshot polling state
	let pollActive = false;
	let pollTimer: ReturnType<typeof setTimeout> | null = null;
	let fps = $state(0);
	let frameTimestamps: number[] = [];
	// Pipelined fetching: allow up to 2 in-flight requests so the next fetch
	// overlaps with decode/render of the current frame, roughly doubling FPS.
	let inFlightCount = 0;
	const MAX_IN_FLIGHT = 2;
	// Track whether direct go2rtc snapshot works (avoids retrying on CORS failure)
	let directSnapshotFailed = false;
	// Cache canvas context to avoid getContext() per frame
	let canvasCtx: CanvasRenderingContext2D | null = null;

	onMount(async () => {
		await loadCamera();
		document.addEventListener('visibilitychange', onVisibility);
		document.addEventListener('fullscreenchange', onFullscreenChange);
	});

	onDestroy(() => {
		stopPolling();
		clearMjpegLoadTimer();
		if (retryTimer) clearTimeout(retryTimer);
		document.removeEventListener('visibilitychange', onVisibility);
		document.removeEventListener('fullscreenchange', onFullscreenChange);
	});

	function onVisibility() {
		if (document.hidden) {
			paused = true;
			stopPolling();
			clearMjpegLoadTimer();
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

	function clearMjpegLoadTimer() {
		if (mjpegLoadTimer) {
			clearTimeout(mjpegLoadTimer);
			mjpegLoadTimer = null;
		}
	}

	async function loadCamera() {
		loading = true;
		error = '';
		try {
			const urls = await api.getCameraUrls();
			mjpegUrl = urls.mjpeg || '';
			proxyUrl = urls.proxy || '';
			snapshotUrl = urls.snapshot || '/api/camera/snapshot';
			snapshotDirectUrl = urls.snapshot_direct || '';

			// Default to MJPEG direct for best performance (native browser decoding,
			// no per-frame proxy overhead). Falls back automatically on failure.
			if (mjpegUrl) {
				streamMode = 'mjpeg-direct';
				loading = false;
				// Start a timeout — if no frame arrives, fall back to proxy
				startMjpegLoadTimer();
			} else if (proxyUrl) {
				streamMode = 'mjpeg-proxy';
				loading = false;
				startMjpegLoadTimer();
			} else {
				streamMode = 'snapshot';
				startPolling();
			}
			retryCount = 0;
		} catch (e) {
			error = 'Camera not available';
			loading = false;
		}
	}

	function startMjpegLoadTimer() {
		clearMjpegLoadTimer();
		mjpegLoadTimer = setTimeout(() => {
			// No frame loaded in time — trigger fallback
			if (loading || (!error && streamMode.startsWith('mjpeg'))) {
				onImgError();
			}
		}, MJPEG_LOAD_TIMEOUT);
	}

	function switchMode(mode: StreamMode) {
		stopPolling();
		clearMjpegLoadTimer();
		if (retryTimer) { clearTimeout(retryTimer); retryTimer = null; }
		if (imgEl) imgEl.src = '';
		streamMode = mode;
		error = '';
		loading = true;

		if (mode === 'snapshot') {
			startPolling();
		} else {
			loading = false;
			startMjpegLoadTimer();
		}
	}

	// ── Snapshot polling with canvas rendering ──────────────────

	function startPolling() {
		if (pollActive) return;
		pollActive = true;
		inFlightCount = 0;
		canvasCtx = null;
		frameTimestamps = [];
		// Kick off 2 fetches immediately to fill the pipeline
		pollNext();
		pollNext();
	}

	function stopPolling() {
		pollActive = false;
		inFlightCount = 0;
		if (pollTimer) {
			clearTimeout(pollTimer);
			pollTimer = null;
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

	function getSnapshotUrl(): string {
		// Try direct go2rtc URL first (bypasses Python proxy, much faster).
		// Falls back to proxy URL on CORS or network failure.
		if (snapshotDirectUrl && !directSnapshotFailed) {
			return `${snapshotDirectUrl}&t=${Date.now()}`;
		}
		return `${snapshotUrl}?t=${Date.now()}`;
	}

	function pollNext() {
		if (!pollActive || paused || inFlightCount >= MAX_IN_FLIGHT) return;
		inFlightCount++;

		const url = getSnapshotUrl();
		const usingDirect = url.includes(':1984');

		const headers: Record<string, string> = {};
		if (!usingDirect) {
			const apiKey = typeof localStorage !== 'undefined' ? localStorage.getItem('printforge:apiKey') : null;
			if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`;
		}

		fetch(url, { headers })
			.then(r => {
				if (!r.ok) throw new Error(`HTTP ${r.status}`);
				return r.blob();
			})
			.then(blob => {
				// Pipeline: blob received = network done. Start next fetch NOW
				// so it overlaps with decode/render of this frame.
				inFlightCount--;
				if (pollActive && !paused) {
					pollTimer = setTimeout(pollNext, 0);
				}
				return blobToDrawable(blob);
			})
			.then(drawable => {
				if (!pollActive) {
					if ('close' in drawable) drawable.close();
					return;
				}

				// Cache and reuse the 2d context
				if (canvasEl) {
					if (!canvasCtx) canvasCtx = canvasEl.getContext('2d');
					if (canvasCtx) {
						const w = drawable instanceof HTMLImageElement ? drawable.naturalWidth : drawable.width;
						const h = drawable instanceof HTMLImageElement ? drawable.naturalHeight : drawable.height;
						if (canvasEl.width !== w || canvasEl.height !== h) {
							canvasEl.width = w;
							canvasEl.height = h;
							// Canvas resize clears context, must re-acquire
							canvasCtx = canvasEl.getContext('2d');
						}
						canvasCtx!.drawImage(drawable, 0, 0);
					}
				}
				if ('close' in drawable) drawable.close();

				loading = false;
				error = '';
				retryCount = 0;

				// Track FPS (lightweight: just push/shift instead of filter)
				const now = performance.now();
				frameTimestamps.push(now);
				while (frameTimestamps.length > 0 && frameTimestamps[0] <= now - 2000) {
					frameTimestamps.shift();
				}
				fps = Math.round(frameTimestamps.length / 2);
			})
			.catch(() => {
				inFlightCount--;
				if (!pollActive) return;

				// If direct URL failed, switch to proxied snapshots
				if (usingDirect && !directSnapshotFailed) {
					directSnapshotFailed = true;
					pollTimer = setTimeout(pollNext, 0);
					return;
				}

				retryCount++;
				if (retryCount >= MAX_RETRIES) {
					error = 'Camera stream unavailable';
					stopPolling();
					return;
				}
				const delay = Math.min(1000 * retryCount, 5000);
				pollTimer = setTimeout(pollNext, delay);
			});
	}

	// ── MJPEG error handling ───────────────────────────────────

	function onImgError() {
		clearMjpegLoadTimer();
		if (streamMode === 'mjpeg-direct' && proxyUrl) {
			// Direct failed — try proxied MJPEG
			streamMode = 'mjpeg-proxy';
			startMjpegLoadTimer();
			return;
		}
		if (streamMode === 'mjpeg-proxy') {
			// Proxy MJPEG also failed — fall back to snapshot polling
			switchMode('snapshot');
			return;
		}
		error = 'Camera stream unavailable';
		scheduleRetry();
	}

	function onImgLoad() {
		clearMjpegLoadTimer();
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
		directSnapshotFailed = false;
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
		streamMode === 'snapshot' ? `SNAP ${fps}fps` :
		streamMode === 'mjpeg-direct' ? 'MJPEG Direct' :
		'MJPEG Proxy'
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
