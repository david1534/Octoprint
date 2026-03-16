<script lang="ts">
	import type { Snippet } from 'svelte';

	interface Props {
		icon?: Snippet;
		title: string;
		description?: string;
		action?: Snippet;
	}

	let { icon, title, description = '', action }: Props = $props();
</script>

<div class="flex flex-col items-center justify-center py-16 text-center">
	{#if icon}
		<div class="w-16 h-16 bg-surface-800 rounded-2xl flex items-center justify-center mb-4">
			{@render icon()}
		</div>
	{/if}
	<h2 class="text-lg font-semibold text-surface-300 mb-2">{title}</h2>
	{#if description}
		<p class="text-sm text-surface-500 mb-4 max-w-sm">{description}</p>
	{/if}
	{#if action}
		{@render action()}
	{/if}
</div>
