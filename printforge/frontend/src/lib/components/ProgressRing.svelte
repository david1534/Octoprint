<script lang="ts">
	interface Props {
		progress?: number;
		size?: number;
		strokeWidth?: number;
		color?: string;
		trackColor?: string;
		showLabel?: boolean;
	}

	let {
		progress = 0,
		size = 120,
		strokeWidth = 8,
		color = '#3b82f6',
		trackColor = '#1e293b',
		showLabel = true
	}: Props = $props();

	let radius = $derived((size - strokeWidth) / 2);
	let circumference = $derived(2 * Math.PI * radius);
	let offset = $derived(circumference - (Math.min(Math.max(progress, 0), 100) / 100) * circumference);
	let center = $derived(size / 2);
</script>

<div class="relative inline-flex items-center justify-center" style="width: {size}px; height: {size}px;">
	<svg width={size} height={size} class="-rotate-90">
		<!-- Track -->
		<circle
			cx={center}
			cy={center}
			r={radius}
			fill="none"
			stroke={trackColor}
			stroke-width={strokeWidth}
		/>
		<!-- Progress -->
		<circle
			cx={center}
			cy={center}
			r={radius}
			fill="none"
			stroke={color}
			stroke-width={strokeWidth}
			stroke-dasharray={circumference}
			stroke-dashoffset={offset}
			stroke-linecap="round"
			class="transition-all duration-500 ease-out"
		/>
	</svg>
	{#if showLabel}
		<div class="absolute inset-0 flex items-center justify-center">
			<span class="text-2xl font-bold tabular-nums text-surface-100">{Math.round(progress)}%</span>
		</div>
	{/if}
</div>
