<script lang="ts">
	import { onMount } from 'svelte';
	import BedMesh from '$lib/components/BedMesh.svelte';
	import { printerState, isConnected } from '$lib/stores/printer';
	import { api } from '$lib/api';
	import { toast } from '$lib/stores/toast';

	let connected = $derived($isConnected);
	let state = $derived($printerState);
	let meshData = $state<any>(null);
	let probing = $state(false);
	let loading = $state(true);

	// Sync mesh data from WebSocket state
	$effect(() => {
		if (state.bed_mesh && state.bed_mesh.grid) {
			meshData = state.bed_mesh;
		}
	});

	onMount(async () => {
		await loadMesh();
	});

	async function loadMesh() {
		loading = true;
		try {
			const data = await api.getBedMesh();
			if (data && data.grid) {
				meshData = data;
			}
		} catch (e: any) {
			// Not critical — mesh may not exist yet
		} finally {
			loading = false;
		}
	}

	async function probeMesh() {
		probing = true;
		toast.info('Starting bed mesh probe. This takes 2-5 minutes...');
		try {
			const data = await api.probeBedMesh();
			if (data && data.grid) {
				meshData = data;
				toast.success('Bed mesh probe complete');
			} else if (data.error) {
				toast.warning(data.error);
			}
		} catch (e: any) {
			toast.error('Probe failed: ' + e.message);
		} finally {
			probing = false;
		}
	}
</script>

<svelte:head>
	<title>PrintForge - Bed Mesh</title>
</svelte:head>

{#if !connected}
	<div class="max-w-md mx-auto mt-20 text-center fade-in">
		<p class="text-surface-400 mb-4">Connect to the printer to view bed mesh data</p>
		<a href="/settings" class="btn-primary inline-block">Go to Settings</a>
	</div>
{:else}
	<div class="space-y-4 fade-in max-w-2xl mx-auto">
		<!-- Header -->
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-lg font-semibold text-surface-100">Bed Mesh</h1>
				<p class="text-sm text-surface-500">Auto bed leveling topography map</p>
			</div>
			<button
				class="btn-primary inline-flex items-center gap-2 text-sm"
				onclick={probeMesh}
				disabled={probing || state.status !== 'idle'}
				title={state.status !== 'idle' ? 'Printer must be idle to probe' : 'Run bed leveling probe (G28 + G29)'}
			>
				{#if probing}
					<span class="animate-spin rounded-full h-4 w-4 border-2 border-white/30 border-t-white"></span>
					Probing...
				{:else}
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
					</svg>
					Probe Bed
				{/if}
			</button>
		</div>

		{#if loading && !meshData}
			<div class="card py-12 text-center">
				<div class="animate-spin rounded-full h-8 w-8 border-2 border-surface-600 border-t-accent mx-auto mb-3"></div>
				<p class="text-surface-400 text-sm">Loading mesh data...</p>
			</div>
		{:else}
			<BedMesh mesh={meshData} />
		{/if}

		<!-- Info card -->
		<div class="card">
			<h3 class="text-sm font-semibold text-surface-300 mb-2">How It Works</h3>
			<div class="text-xs text-surface-500 space-y-1">
				<p>The bed mesh is captured automatically when G29 runs during the print start procedure. You can also trigger a fresh probe manually with the button above.</p>
				<p>The heatmap shows Z-offset at each probe point. <span class="text-blue-400">Blue</span> = low, <span class="text-emerald-400">green</span> = level, <span class="text-red-400">red</span> = high. Marlin automatically compensates for these differences during printing when the mesh is active.</p>
				<p>A variance under 0.1mm is excellent. Over 0.6mm indicates the bed may need physical adjustment.</p>
			</div>
		</div>
	</div>
{/if}
