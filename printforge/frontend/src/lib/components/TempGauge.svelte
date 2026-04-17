<script lang="ts">
	interface Props {
		label: string;
		actual: number;
		target: number;
		maxTemp?: number;
		color?: string;
		onclick?: () => void;
		title?: string;
	}

	let { label, actual, target, maxTemp = 300, color = '#3b82f6', onclick, title }: Props = $props();

	let percentage = $derived(Math.min(100, (actual / maxTemp) * 100));
	let isHeating = $derived(target > 0 && actual < target - 2);
	let isAtTarget = $derived(target > 0 && Math.abs(actual - target) <= 2);
</script>

{#snippet content()}
	<div class="flex items-center justify-between">
		<span class="text-sm font-medium text-surface-400">{label}</span>
		{#if isHeating}
			<span class="badge bg-amber-500/20 text-amber-400">Heating</span>
		{:else if isAtTarget}
			<span class="badge bg-emerald-500/20 text-emerald-400">Ready</span>
		{/if}
	</div>

	<div class="flex items-end gap-1">
		<span class="text-3xl font-bold tabular-nums">{actual.toFixed(1)}</span>
		<span class="text-surface-500 text-lg mb-0.5">°C</span>
	</div>

	{#if target > 0}
		<div class="text-sm text-surface-400">
			Target: <span class="text-surface-200">{target.toFixed(0)}°C</span>
		</div>
	{/if}

	<!-- Progress bar -->
	<div class="w-full h-2 bg-surface-800 rounded-full overflow-hidden">
		<div
			class="h-full rounded-full transition-all duration-500"
			style="width: {percentage}%; background-color: {color}"
		></div>
	</div>
{/snippet}

{#if onclick}
	<button
		type="button"
		{onclick}
		{title}
		class="card flex flex-col gap-2 text-left w-full h-full transition-colors
		       hover:bg-surface-800/60 hover:border-surface-600
		       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
	>
		{@render content()}
	</button>
{:else}
	<div class="card flex flex-col gap-2 h-full">
		{@render content()}
	</div>
{/if}
