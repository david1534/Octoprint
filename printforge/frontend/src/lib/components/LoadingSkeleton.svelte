<script lang="ts">
	interface Props {
		lines?: number;
		height?: string;
		width?: string;
		rounded?: string;
	}

	let { lines = 3, height = 'h-4', width = 'w-full', rounded = 'rounded' }: Props = $props();
</script>

<div class="space-y-3 animate-pulse">
	{#each Array(lines) as _, i}
		<div
			class="bg-surface-800 {height} {i === lines - 1 && lines > 1 ? 'w-2/3' : width} {rounded}"
		></div>
	{/each}
</div>
