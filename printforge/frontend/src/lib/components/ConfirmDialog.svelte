<script lang="ts">
	import { fade, scale } from 'svelte/transition';
	import { confirmState, resolveConfirm } from '../stores/confirm';

	let state = $derived($confirmState);

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && state.open) {
			resolveConfirm(false);
		}
	}
</script>

<svelte:window onkeydown={onKeydown} />

{#if state.open}
	<!-- Backdrop -->
	<div
		class="fixed inset-0 z-[200] flex items-center justify-center p-4"
		transition:fade={{ duration: 150 }}
	>
		<!-- eslint-disable-next-line -->
		<div class="absolute inset-0 bg-black/60 backdrop-blur-sm" onclick={() => resolveConfirm(false)}></div>

		<!-- Dialog -->
		<div
			class="relative bg-surface-900 border border-surface-700 rounded-xl p-6 w-full max-w-sm shadow-2xl"
			transition:scale={{ start: 0.95, duration: 150 }}
		>
			<h3 class="text-lg font-semibold text-surface-100 mb-2">{state.title}</h3>
			<p class="text-sm text-surface-400 mb-6">{state.message}</p>
			<div class="flex gap-3 justify-end">
				<button class="btn-secondary text-sm" onclick={() => resolveConfirm(false)}>
					Cancel
				</button>
				<button
					class="{state.variant === 'danger' ? 'btn-danger' : 'btn-primary'} text-sm"
					onclick={() => resolveConfirm(true)}
				>
					{state.confirmLabel}
				</button>
			</div>
		</div>
	</div>
{/if}
