<script lang="ts">
	import { onMount } from 'svelte';
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

	let timelapses = $state<Timelapse[]>([]);
	let loading = $state(true);
	let activeVideo = $state<string | null>(null);
	let deleting = $state('');

	onMount(async () => {
		await loadTimelapses();
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
		// Remove timestamp suffix and extension: "filename_20250301181752.mp4" -> "filename"
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
</script>

<svelte:head>
	<title>PrintForge - Timelapses</title>
</svelte:head>

<div class="flex items-center justify-between mb-6">
	<h1 class="text-xl font-bold">Timelapses</h1>
	<span class="text-sm text-surface-500">{timelapses.length} video{timelapses.length !== 1 ? 's' : ''}</span>
</div>

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
		title="No Timelapses"
		description="Timelapse videos from your prints will appear here"
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
					<!-- Duration badge -->
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
