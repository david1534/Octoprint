<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { api } from '$lib/api';
	import { toast } from '$lib/stores/toast';
	import { confirmAction } from '$lib/stores/confirm';
	import { formatFileSize, formatTimeAgo } from '$lib/utils';
	import EmptyState from '$lib/components/EmptyState.svelte';

	interface Timelapse {
		filename: string;
		size: number;
		date: number;
		hasThumbnail: boolean;
	}

	interface RecordingStatus {
		recording: boolean;
		assembling: boolean;
		frameCount: number;
		printFile: string;
		captureMode: string;
		captureInterval: number;
		renderFps: number;
		enabled: boolean;
		lastVideo: string | null;
		elapsed: number;
	}

	let timelapses = $state<Timelapse[]>([]);
	let loading = $state(true);
	let activeVideo = $state<string | null>(null);
	let deleting = $state('');
	let showSettings = $state(false);
	let testingCapture = $state(false);

	// Recording status
	let recStatus = $state<RecordingStatus | null>(null);
	let statusTimer: ReturnType<typeof setInterval> | null = null;

	// Settings form
	let settingsForm = $state({
		enabled: true,
		captureMode: 'on_layer',
		captureInterval: 10,
		renderFps: 30,
	});
	let savingSettings = $state(false);

	onMount(() => {
		Promise.all([loadTimelapses(), loadRecordingStatus()]);
		// Poll recording status every 3s
		statusTimer = setInterval(loadRecordingStatus, 3000);
	});

	onDestroy(() => {
		if (statusTimer) clearInterval(statusTimer);
	});

	async function loadTimelapses() {
		loading = true;
		try {
			const data = await api.listTimelapses();
			timelapses = data.timelapses || [];
		} catch (e: any) {
			toast.error('Failed to load timelapses: ' + e.message);
		} finally {
			loading = false;
		}
	}

	async function loadRecordingStatus() {
		try {
			recStatus = await api.getTimelapseRecordingStatus();
			if (recStatus && !showSettings) {
				settingsForm = {
					enabled: recStatus.enabled,
					captureMode: recStatus.captureMode,
					captureInterval: recStatus.captureInterval,
					renderFps: recStatus.renderFps,
				};
			}
		} catch {
			// Not critical
		}
	}

	async function saveSettings() {
		savingSettings = true;
		try {
			await api.updateTimelapseSettings(settingsForm);
			toast.success('Timelapse settings saved');
			await loadRecordingStatus();
			showSettings = false;
		} catch (e: any) {
			toast.error('Failed to save settings: ' + e.message);
		} finally {
			savingSettings = false;
		}
	}

	async function testCapture() {
		testingCapture = true;
		try {
			const result = await api.testTimelapseCapture();
			toast.success(`Test frame captured (${formatFileSize(result.size)})`);
		} catch (e: any) {
			toast.error('Test capture failed: ' + e.message);
		} finally {
			testingCapture = false;
		}
	}

	async function deleteTimelapse(t: Timelapse) {
		const ok = await confirmAction({
			title: 'Delete Timelapse',
			message: `Delete "${t.filename}"? This cannot be undone.`,
			confirmLabel: 'Delete',
			variant: 'danger'
		});
		if (!ok) return;
		deleting = t.filename;
		try {
			await api.deleteTimelapse(t.filename);
			timelapses = timelapses.filter(x => x.filename !== t.filename);
			if (activeVideo === t.filename) activeVideo = null;
			toast.success('Deleted: ' + t.filename);
		} catch (e: any) {
			toast.error('Delete failed: ' + e.message);
		} finally {
			deleting = '';
		}
	}

	function prettyName(filename: string): string {
		return filename
			.replace(/\.mp4$|\.mkv$|\.webm$/i, '')
			.replace(/_\d{14}(-fail)?$/, '')
			.replace(/_/g, ' ');
	}

	function formatDate(ts: number): string {
		return new Date(ts * 1000).toLocaleDateString(undefined, {
			year: 'numeric', month: 'short', day: 'numeric',
			hour: '2-digit', minute: '2-digit'
		});
	}

	function formatElapsed(seconds: number): string {
		const m = Math.floor(seconds / 60);
		const s = Math.floor(seconds % 60);
		return m > 0 ? `${m}m ${s}s` : `${s}s`;
	}
</script>

<svelte:head>
	<title>PrintForge - Timelapses</title>
</svelte:head>

<div class="flex items-center justify-between mb-6">
	<h1 class="text-xl font-bold">Timelapses</h1>
	<div class="flex items-center gap-3">
		<span class="text-sm text-surface-500">{timelapses.length} video{timelapses.length !== 1 ? 's' : ''}</span>
		<button
			class="btn-secondary text-xs px-3 py-1.5 inline-flex items-center gap-1.5"
			onclick={() => showSettings = !showSettings}
		>
			<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
			</svg>
			Settings
		</button>
	</div>
</div>

<!-- Recording status banner -->
{#if recStatus?.recording}
	<div class="card bg-gradient-to-r from-red-500/10 to-surface-900 border-red-500/20 mb-4">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-3">
				<div class="relative">
					<div class="w-3 h-3 bg-red-500 rounded-full"></div>
					<div class="absolute inset-0 w-3 h-3 bg-red-500 rounded-full animate-ping opacity-75"></div>
				</div>
				<div>
					<p class="text-sm font-medium text-surface-200">Recording Timelapse</p>
					<p class="text-xs text-surface-400">
						{recStatus.printFile} &middot;
						{recStatus.frameCount} frames &middot;
						{formatElapsed(recStatus.elapsed)} &middot;
						{recStatus.captureMode === 'on_layer' ? 'Layer change' : `Every ${recStatus.captureInterval}s`}
					</p>
				</div>
			</div>
		</div>
	</div>
{:else if recStatus?.assembling}
	<div class="card bg-gradient-to-r from-amber-500/10 to-surface-900 border-amber-500/20 mb-4">
		<div class="flex items-center gap-3">
			<span class="animate-spin rounded-full h-5 w-5 border-2 border-amber-500/30 border-t-amber-500"></span>
			<div>
				<p class="text-sm font-medium text-surface-200">Assembling Video</p>
				<p class="text-xs text-surface-400">Creating timelapse from {recStatus.frameCount} frames...</p>
			</div>
		</div>
	</div>
{/if}

<!-- Settings panel -->
{#if showSettings}
	<div class="card mb-6">
		<h2 class="text-sm font-semibold text-surface-300 mb-4">Timelapse Settings</h2>
		<div class="space-y-4">
			<!-- Enable/disable -->
			<label class="flex items-center justify-between">
				<span class="text-sm text-surface-300">Enable timelapse recording</span>
				<button
					class="w-10 h-5 rounded-full transition-colors {settingsForm.enabled ? 'bg-accent' : 'bg-surface-700'}"
					onclick={() => settingsForm.enabled = !settingsForm.enabled}
				>
					<div class="w-4 h-4 bg-white rounded-full transition-transform ml-0.5 {settingsForm.enabled ? 'translate-x-5' : ''}"></div>
				</button>
			</label>

			<!-- Capture mode -->
			<div>
				<label class="text-sm text-surface-400 block mb-1.5">Capture Mode</label>
				<div class="flex gap-2">
					<button
						class="flex-1 px-3 py-2 rounded-lg text-sm text-center transition-colors
							   {settingsForm.captureMode === 'on_layer' ? 'bg-accent/20 text-accent border border-accent/30' : 'bg-surface-800 text-surface-400 border border-surface-700 hover:border-surface-600'}"
						onclick={() => settingsForm.captureMode = 'on_layer'}
					>
						On Layer Change
					</button>
					<button
						class="flex-1 px-3 py-2 rounded-lg text-sm text-center transition-colors
							   {settingsForm.captureMode === 'timed' ? 'bg-accent/20 text-accent border border-accent/30' : 'bg-surface-800 text-surface-400 border border-surface-700 hover:border-surface-600'}"
						onclick={() => settingsForm.captureMode = 'timed'}
					>
						Timed Interval
					</button>
				</div>
			</div>

			<!-- Interval (only for timed mode) -->
			{#if settingsForm.captureMode === 'timed'}
				<div>
					<label for="interval" class="text-sm text-surface-400 block mb-1.5">
						Capture Interval: {settingsForm.captureInterval}s
					</label>
					<input
						id="interval"
						type="range"
						min="1"
						max="60"
						step="1"
						bind:value={settingsForm.captureInterval}
						class="w-full accent-accent"
					/>
					<div class="flex justify-between text-xs text-surface-600 mt-0.5">
						<span>1s</span>
						<span>30s</span>
						<span>60s</span>
					</div>
				</div>
			{/if}

			<!-- Render FPS -->
			<div>
				<label for="fps" class="text-sm text-surface-400 block mb-1.5">
					Video FPS: {settingsForm.renderFps}
				</label>
				<input
					id="fps"
					type="range"
					min="10"
					max="60"
					step="5"
					bind:value={settingsForm.renderFps}
					class="w-full accent-accent"
				/>
				<div class="flex justify-between text-xs text-surface-600 mt-0.5">
					<span>10</span>
					<span>30</span>
					<span>60</span>
				</div>
			</div>

			<!-- Actions -->
			<div class="flex gap-2 pt-2">
				<button
					class="btn-primary text-sm px-4 py-2"
					onclick={saveSettings}
					disabled={savingSettings}
				>
					{savingSettings ? 'Saving...' : 'Save Settings'}
				</button>
				<button
					class="btn-secondary text-sm px-4 py-2 inline-flex items-center gap-1.5"
					onclick={testCapture}
					disabled={testingCapture}
				>
					{#if testingCapture}
						<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-surface-400 border-t-white"></span>
					{/if}
					Test Capture
				</button>
				<button
					class="btn-secondary text-sm px-4 py-2"
					onclick={() => showSettings = false}
				>
					Close
				</button>
			</div>
		</div>
	</div>
{/if}

<!-- Video player -->
{#if activeVideo}
	<div class="card mb-6">
		<div class="flex items-center justify-between mb-3">
			<h2 class="text-sm font-medium text-surface-300 truncate">{prettyName(activeVideo)}</h2>
			<button
				class="btn-icon p-1.5"
				onclick={() => activeVideo = null}
				title="Close"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M6 18L18 6M6 6l12 12" />
				</svg>
			</button>
		</div>
		<!-- svelte-ignore a11y_media_has_caption -->
		<video
			class="w-full rounded-lg bg-black max-h-[70vh]"
			controls
			autoplay
			src={api.getTimelapseVideoUrl(activeVideo)}
		>
		</video>
	</div>
{/if}

{#if loading}
	<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
		{#each Array(6) as _}
			<div class="card">
				<div class="aspect-video bg-surface-800 rounded-lg animate-pulse mb-3"></div>
				<div class="h-4 bg-surface-800 rounded animate-pulse w-3/4 mb-2"></div>
				<div class="h-3 bg-surface-800 rounded animate-pulse w-1/2"></div>
			</div>
		{/each}
	</div>
{:else if timelapses.length === 0}
	<EmptyState
		title="No Timelapses Yet"
		description={recStatus?.enabled
			? "Timelapse videos will be automatically created during your prints. Start a print to see them here."
			: "Timelapse recording is disabled. Enable it in settings above to automatically capture timelapses during prints."}
	>
		{#snippet icon()}
			<svg class="w-8 h-8 text-surface-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
			</svg>
		{/snippet}
	</EmptyState>
{:else}
	<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
		{#each timelapses as t}
			<div class="card group">
				<!-- Thumbnail / play button -->
				<button
					class="w-full aspect-video bg-surface-800 rounded-lg mb-3 relative overflow-hidden
						   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
					onclick={() => activeVideo = t.filename}
				>
					{#if t.hasThumbnail}
						<img
							src={api.getTimelapseThumbnailUrl(t.filename)}
							alt={prettyName(t.filename)}
							class="w-full h-full object-cover rounded-lg"
							loading="lazy"
						/>
					{:else}
						<div class="w-full h-full flex items-center justify-center">
							<svg class="w-12 h-12 text-surface-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
							</svg>
						</div>
					{/if}
					<!-- Play overlay -->
					<div class="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 group-hover:opacity-100 transition-opacity">
						<div class="w-12 h-12 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center">
							<svg class="w-6 h-6 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24">
								<path d="M8 5v14l11-7z" />
							</svg>
						</div>
					</div>
					<!-- Size badge -->
					<span class="absolute bottom-2 right-2 text-xs bg-black/70 text-white px-1.5 py-0.5 rounded">
						{formatFileSize(t.size)}
					</span>
					{#if t.filename.includes('-fail')}
						<span class="absolute top-2 left-2 text-xs bg-red-500/80 text-white px-1.5 py-0.5 rounded font-medium">
							Failed
						</span>
					{/if}
				</button>

				<!-- Info -->
				<div class="flex items-start justify-between gap-2">
					<div class="min-w-0">
						<p class="text-sm text-surface-200 font-medium truncate" title={t.filename}>{prettyName(t.filename)}</p>
						<p class="text-xs text-surface-500 mt-0.5">{formatDate(t.date)}</p>
					</div>
					<div class="flex gap-1 shrink-0">
						<a
							href={api.getTimelapseVideoUrl(t.filename)}
							download={t.filename}
							class="btn-icon p-1.5"
							title="Download"
						>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
							</svg>
						</a>
						<button
							class="btn-icon p-1.5 text-red-400/50 hover:text-red-400"
							onclick={() => deleteTimelapse(t)}
							disabled={deleting === t.filename}
							title="Delete"
						>
							{#if deleting === t.filename}
								<span class="animate-spin rounded-full h-4 w-4 border-2 border-red-400/30 border-t-red-400"></span>
							{:else}
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
								</svg>
							{/if}
						</button>
					</div>
				</div>
			</div>
		{/each}
	</div>
{/if}
