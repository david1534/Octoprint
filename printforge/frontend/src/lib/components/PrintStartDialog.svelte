<script lang="ts">
	import { fade, scale } from 'svelte/transition';
	import { api } from '$lib/api';

	interface Spool {
		id: number;
		name: string;
		material: string;
		color: string;
		total_weight_g: number;
		used_weight_g: number;
		cost_per_kg: number;
		active: number;
		notes: string;
	}

	interface Props {
		open: boolean;
		filename: string;
		onconfirm: (spoolId: number | null) => void;
		oncancel: () => void;
	}

	let { open = $bindable(), filename, onconfirm, oncancel }: Props = $props();

	let spools = $state<Spool[]>([]);
	let loading = $state(true);
	let selectedSpoolId = $state<number | null>(null);
	let warningThreshold = $state(50);

	$effect(() => {
		if (open) {
			loadSpools();
		}
	});

	async function loadSpools() {
		loading = true;
		try {
			const [spoolData, warningData] = await Promise.all([
				api.getSpools(),
				api.getLowFilamentWarnings(),
			]);
			spools = spoolData.spools || [];
			warningThreshold = warningData.threshold_g || 50;
			// Default to active spool
			const activeSpool = spools.find(s => s.active);
			selectedSpoolId = activeSpool?.id ?? null;
		} catch {
			spools = [];
		} finally {
			loading = false;
		}
	}

	function remaining(spool: Spool): number {
		return Math.max(0, spool.total_weight_g - spool.used_weight_g);
	}

	function remainingPct(spool: Spool): number {
		if (spool.total_weight_g <= 0) return 0;
		return Math.min(100, Math.max(0, (remaining(spool) / spool.total_weight_g) * 100));
	}

	function isLow(spool: Spool): boolean {
		return remaining(spool) <= warningThreshold;
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && open) {
			oncancel();
		}
	}
</script>

<svelte:window onkeydown={onKeydown} />

{#if open}
	<div
		class="fixed inset-0 z-[200] flex items-center justify-center p-4"
		transition:fade={{ duration: 150 }}
	>
		<!-- eslint-disable-next-line -->
		<div class="absolute inset-0 bg-black/60 backdrop-blur-sm" onclick={oncancel}></div>

		<div
			class="relative bg-surface-900 border border-surface-700 rounded-xl p-6 w-full max-w-md shadow-2xl"
			transition:scale={{ start: 0.95, duration: 150 }}
		>
			<h3 class="text-lg font-semibold text-surface-100 mb-1">Start Print</h3>
			<p class="text-sm text-surface-400 mb-4 truncate" title={filename}>
				{filename}
			</p>

			<!-- Spool Selection -->
			<div class="mb-4">
				<label class="block text-sm text-surface-400 mb-2">Filament Spool</label>
				{#if loading}
					<div class="text-xs text-surface-500">Loading spools...</div>
				{:else if spools.length === 0}
					<div class="text-xs text-surface-500 bg-surface-800/50 rounded-lg p-3">
						No spools configured. Filament tracking will be skipped.
					</div>
				{:else}
					<div class="space-y-1.5 max-h-48 overflow-y-auto pr-1">
						<!-- No spool option -->
						<button
							class="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors
								{selectedSpoolId === null ? 'bg-accent/10 ring-1 ring-accent/40' : 'bg-surface-800/50 hover:bg-surface-800'}"
							onclick={() => selectedSpoolId = null}
						>
							<div class="w-5 h-5 rounded-full border-2 border-dashed border-surface-600 shrink-0"></div>
							<span class="text-sm text-surface-400">No spool (skip tracking)</span>
						</button>

						{#each spools as spool (spool.id)}
							{@const low = isLow(spool)}
							<button
								class="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-colors
									{selectedSpoolId === spool.id ? 'bg-accent/10 ring-1 ring-accent/40' : 'bg-surface-800/50 hover:bg-surface-800'}"
								onclick={() => selectedSpoolId = spool.id}
							>
								<div
									class="w-5 h-5 rounded-full shrink-0 border border-surface-600"
									style="background-color: {spool.color}"
								></div>
								<div class="flex-1 min-w-0">
									<div class="flex items-center gap-1.5">
										<span class="text-sm text-surface-200 truncate">{spool.name}</span>
										<span class="text-[10px] px-1 py-0.5 rounded bg-surface-700 text-surface-400">{spool.material}</span>
										{#if spool.active}
											<span class="text-[10px] px-1 py-0.5 rounded bg-accent/20 text-accent">Active</span>
										{/if}
										{#if low}
											<span class="text-[10px] px-1 py-0.5 rounded bg-amber-500/20 text-amber-400">Low</span>
										{/if}
									</div>
									<div class="flex items-center gap-2 mt-0.5">
										<div class="flex-1 h-1.5 bg-surface-700 rounded-full overflow-hidden">
											<div
												class="h-full rounded-full {remainingPct(spool) > 20 ? 'bg-accent' : remainingPct(spool) > 5 ? 'bg-amber-500' : 'bg-red-500'}"
												style="width: {remainingPct(spool)}%"
											></div>
										</div>
										<span class="text-[10px] text-surface-500 tabular-nums shrink-0">
											{remaining(spool).toFixed(0)}g left
										</span>
									</div>
								</div>
							</button>
						{/each}
					</div>
				{/if}
			</div>

			{#if selectedSpoolId !== null}
				{@const sel = spools.find(s => s.id === selectedSpoolId)}
				{#if sel && isLow(sel)}
					<div class="flex items-start gap-2 mb-4 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
						<svg class="w-4 h-4 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
						</svg>
						<p class="text-xs text-amber-300">
							Low filament warning: only {remaining(sel).toFixed(0)}g remaining on "{sel.name}". This may not be enough for the print.
						</p>
					</div>
				{/if}
			{/if}

			<div class="flex gap-3 justify-end">
				<button class="btn-secondary text-sm" onclick={oncancel}>
					Cancel
				</button>
				<button
					class="btn-primary text-sm"
					onclick={() => onconfirm(selectedSpoolId)}
				>
					Start Print
				</button>
			</div>
		</div>
	</div>
{/if}
