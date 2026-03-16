<script lang="ts">
	import JogControls from '$lib/components/JogControls.svelte';
	import TemperatureControls from '$lib/components/TemperatureControls.svelte';
	import ExtruderControls from '$lib/components/ExtruderControls.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import { printerState, isConnected } from '$lib/stores/printer';

	let connected = $derived($isConnected);
	let pos = $derived($printerState.position);
</script>

<svelte:head>
	<title>PrintForge - Control</title>
</svelte:head>

<h1 class="text-xl font-bold mb-4">Printer Control</h1>

{#if !connected}
	<EmptyState
		title="Printer Not Connected"
		description="Connect your printer to use the controls"
	>
		{#snippet icon()}
			<svg class="w-8 h-8 text-surface-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
			</svg>
		{/snippet}
		{#snippet action()}
			<a href="/settings" class="btn-primary">Go to Settings</a>
		{/snippet}
	</EmptyState>
{:else}
	<!-- Live Position Bar -->
	<div class="card mb-4 py-3">
		<div class="flex items-center justify-between">
			<h3 class="text-sm font-medium text-surface-400">Live Position</h3>
			<div class="flex gap-6 text-sm tabular-nums">
				<div class="text-center">
					<span class="text-xs text-surface-500">X</span>
					<p class="text-surface-200 font-semibold">{pos.x.toFixed(2)}</p>
				</div>
				<div class="text-center">
					<span class="text-xs text-surface-500">Y</span>
					<p class="text-surface-200 font-semibold">{pos.y.toFixed(2)}</p>
				</div>
				<div class="text-center">
					<span class="text-xs text-surface-500">Z</span>
					<p class="text-surface-200 font-semibold">{pos.z.toFixed(2)}</p>
				</div>
			</div>
		</div>
	</div>

	<!-- Controls grid -->
	<div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
		<JogControls />
		<TemperatureControls />
		<ExtruderControls />
	</div>
{/if}
