<script lang="ts">
	import { fly } from 'svelte/transition';
	import { toasts, dismissToast } from '../stores/toast';

	const icons: Record<string, string> = {
		success: 'M5 13l4 4L19 7',
		error: 'M6 18L18 6M6 6l12 12',
		warning: 'M12 9v2m0 4h.01M12 3l9.5 16.5H2.5L12 3z',
		info: 'M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20 10 10 0 000-20z'
	};

	const colors: Record<string, string> = {
		success: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400',
		error: 'bg-red-500/15 border-red-500/30 text-red-400',
		warning: 'bg-amber-500/15 border-amber-500/30 text-amber-400',
		info: 'bg-accent/15 border-accent/30 text-accent'
	};
</script>

<!-- Mobile: top center, Desktop: bottom right -->
<div class="fixed top-16 left-4 right-4 md:top-auto md:left-auto md:bottom-4 md:right-4 md:w-80 z-[100] flex flex-col gap-2 pointer-events-none">
	{#each $toasts as t (t.id)}
		<div
			class="pointer-events-auto border rounded-lg px-4 py-3 shadow-lg backdrop-blur-sm flex items-start gap-3 {colors[t.type]}"
			transition:fly={{ y: -20, duration: 200 }}
		>
			<svg class="w-5 h-5 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={icons[t.type]} />
			</svg>
			<p class="flex-1 text-sm">{t.message}</p>
			<button class="shrink-0 opacity-60 hover:opacity-100 transition-opacity" onclick={() => dismissToast(t.id)}>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
				</svg>
			</button>
		</div>
	{/each}
</div>
