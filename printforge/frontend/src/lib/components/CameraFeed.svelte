<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { api } from '../api';

	type StreamMode = 'webrtc' | 'mjpeg-direct' | 'mjpeg-proxy';

	let webrtcUrl = $state('');
	let mjpegUrl = $state('');
	let proxyUrl = $state('');
	let streamMode = $state<StreamMode>('webrtc');
	let error = $state('');
	let loading = $state(true);
	let retryCount = $state(0);
	let retryTimer: ReturnType<typeof setTimeout> | null = null;
	let paused = $state(false);
	let fullscreen = $state(false);
	let containerEl: HTMLDivElement;
	let videoEl: HTMLVideoElement;
	let pc: RTCPeerConnection | null = null;
	const MAX_RETRIES = 5;

	onMount(async () => {
		await loadCamera();
		document.addEventListener('visibilitychange', onVisibility);
		document.addEventListener('fullscreenchange', onFullscreenChange);
	});

	onDestroy(() => {
		if (retryTimer) clearTimeout(retryTimer);
		cleanupWebRTC();
		document.removeEventListener('visibilitychange', onVisibility);
		document.removeEventListener('fullscreenchange', onFullscreenChange);
	});

	function cleanupWebRTC() {
		if (pc) {
			pc.close();
			pc = null;
		}
	}

	function onVisibility() {
		if (document.hidden) {
			paused = true;
			cleanupWebRTC();
		} else {
			paused = false;
			if (error || streamMode === 'webrtc') {
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
			webrtcUrl = urls.webrtc || '';
			mjpegUrl = urls.mjpeg || '';
			proxyUrl = urls.proxy || '';

			// Prefer direct MJPEG (lowest latency, most reliable).
			// WebRTC is attempted only if no MJPEG URL is available.
			if (mjpegUrl) {
				streamMode = 'mjpeg-direct';
				loading = false;
			} else if (webrtcUrl) {
				streamMode = 'webrtc';
				await startWebRTC();
			} else if (proxyUrl) {
				streamMode = 'mjpeg-proxy';
				loading = false;
			}
			retryCount = 0;
		} catch (e) {
			error = 'Camera not available';
			loading = false;
		}
	}

	async function startWebRTC() {
		cleanupWebRTC();

		try {
			pc = new RTCPeerConnection({
				iceServers: [{ urls: 'stun:stun.l.google.com:19302' }],
			});

			pc.addTransceiver('video', { direction: 'recvonly' });

			pc.ontrack = (event) => {
				if (videoEl && event.streams[0]) {
					videoEl.srcObject = event.streams[0];
					loading = false;
					error = '';
				}
			};

			pc.oniceconnectionstatechange = () => {
				if (!pc) return;
				const state = pc.iceConnectionState;
				if (state === 'failed' || state === 'disconnected' || state === 'closed') {
					fallbackToMJPEG();
				}
			};

			const offer = await pc.createOffer();
			await pc.setLocalDescription(offer);

			// Wait for ICE gathering to complete (or timeout after 2s)
			await new Promise<void>((resolve) => {
				if (!pc) return resolve();
				if (pc.iceGatheringState === 'complete') return resolve();
				const timeout = setTimeout(resolve, 2000);
				pc.onicegatheringstatechange = () => {
					if (pc?.iceGatheringState === 'complete') {
						clearTimeout(timeout);
						resolve();
					}
				};
			});

			const resp = await fetch(webrtcUrl, {
				method: 'POST',
				headers: { 'Content-Type': 'application/sdp' },
				body: pc.localDescription!.sdp,
			});

			if (!resp.ok) {
				throw new Error(`Signaling failed: ${resp.status}`);
			}

			const answerSdp = await resp.text();
			await pc.setRemoteDescription(
				new RTCSessionDescription({ type: 'answer', sdp: answerSdp })
			);

			// If no video track arrives within 5 seconds, fall back
			setTimeout(() => {
				if (loading && streamMode === 'webrtc') {
					fallbackToMJPEG();
				}
			}, 5000);
		} catch (e) {
			fallbackToMJPEG();
		}
	}

	function fallbackToMJPEG() {
		cleanupWebRTC();
		if (mjpegUrl) {
			streamMode = 'mjpeg-direct';
			loading = false;
		} else if (proxyUrl) {
			streamMode = 'mjpeg-proxy';
			loading = false;
		} else {
			error = 'Camera stream unavailable';
			loading = false;
			scheduleRetry();
		}
	}

	function onImgError() {
		if (streamMode === 'mjpeg-direct' && proxyUrl) {
			streamMode = 'mjpeg-proxy';
			return;
		}
		error = 'Camera stream unavailable';
		scheduleRetry();
	}

	function onImgLoad() {
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
		streamMode === 'webrtc' ? 'WebRTC' :
		streamMode === 'mjpeg-direct' ? 'MJPEG' :
		'proxied'
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
		{:else if streamMode === 'webrtc'}
			<!-- svelte-ignore a11y_media_has_caption -->
			<video
				bind:this={videoEl}
				autoplay
				playsinline
				muted
				class="w-full h-full object-cover"
			></video>
		{:else}
			<img
				src={currentMjpegSrc}
				alt="Printer camera"
				class="w-full h-full object-cover"
				onerror={onImgError}
				onload={onImgLoad}
			/>
		{/if}
	</div>
</div>
