<script lang="ts">
	interface Props {
		label: string;
		color?: 'green' | 'red' | 'amber' | 'blue' | 'gray';
		pulse?: boolean;
		size?: 'sm' | 'md';
	}

	let { label, color = 'gray', pulse = false, size = 'sm' }: Props = $props();

	const dotColors: Record<string, string> = {
		green: 'bg-emerald-400',
		red: 'bg-red-400',
		amber: 'bg-amber-400',
		blue: 'bg-blue-400',
		gray: 'bg-surface-400'
	};

	let dotClass = $derived(`${dotColors[color] || dotColors.gray} ${pulse ? 'animate-pulse' : ''}`);
	let textClass = $derived(size === 'sm' ? 'text-xs' : 'text-sm');
</script>

<div class="inline-flex items-center gap-1.5">
	<div class="w-2 h-2 rounded-full transition-colors duration-300 {dotClass}"></div>
	<span class="{textClass} text-surface-400">{label}</span>
</div>
