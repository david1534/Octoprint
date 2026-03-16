<script lang="ts">
	import { api } from '../api';
	import { printerState } from '../stores/printer';
	import { toast } from '../stores/toast';

	let stepSize = $state(10);
	let feedrate = $state(3000);
	let loading = $state('');
	let isConnected = $derived($printerState.status !== 'disconnected');
	let pos = $derived($printerState.position);

	const steps = [0.1, 1, 10, 100];
	const feedrates = [
		{ label: 'Slow', value: 1000 },
		{ label: 'Normal', value: 3000 },
		{ label: 'Fast', value: 6000 }
	];

	async function jog(axis: string, direction: number) {
		if (loading) return;
		loading = axis + direction;
		try {
			const move: Record<string, number> = {};
			move[axis.toLowerCase()] = stepSize * direction;
			await api.jog(move.x || 0, move.y || 0, move.z || 0, feedrate);
		} catch (e: any) {
			toast.error('Jog failed: ' + e.message);
		} finally {
			loading = '';
		}
	}

	async function homeAll() {
		loading = 'home';
		try {
			await api.home();
			toast.info('Homing all axes');
		} catch (e: any) {
			toast.error('Home failed: ' + e.message);
		} finally {
			loading = '';
		}
	}

	async function homeAxis(axis: string) {
		loading = 'home' + axis;
		try {
			await api.home(axis);
		} catch (e: any) {
			toast.error(`Home ${axis} failed: ` + e.message);
		} finally {
			loading = '';
		}
	}
</script>

<div class="card">
	<div class="flex items-center justify-between mb-3">
		<h3 class="text-sm font-medium text-surface-400">Movement</h3>
		<!-- Live position -->
		<span class="text-xs tabular-nums text-surface-500">
			X:{pos.x.toFixed(1)} Y:{pos.y.toFixed(1)} Z:{pos.z.toFixed(1)}
		</span>
	</div>

	<!-- Step size selector -->
	<div class="mb-3">
		<span class="text-xs text-surface-500 mb-1 block">Step Size</span>
		<div class="flex gap-1">
			{#each steps as step}
				<button
					class="flex-1 py-2.5 min-h-[44px] rounded-lg text-sm font-medium transition-colors
						   {stepSize === step ? 'bg-accent text-white' : 'bg-surface-800 text-surface-400 hover:bg-surface-700'}
						   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
					onclick={() => stepSize = step}
				>
					{step}mm
				</button>
			{/each}
		</div>
	</div>

	<!-- Feedrate selector -->
	<div class="mb-4">
		<span class="text-xs text-surface-500 mb-1 block">Speed</span>
		<div class="flex gap-1">
			{#each feedrates as fr}
				<button
					class="flex-1 py-2 min-h-[36px] rounded-lg text-xs font-medium transition-colors
						   {feedrate === fr.value ? 'bg-surface-700 text-surface-100' : 'bg-surface-800/50 text-surface-500 hover:bg-surface-800 hover:text-surface-300'}
						   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
					onclick={() => feedrate = fr.value}
				>
					{fr.label}
				</button>
			{/each}
		</div>
	</div>

	<!-- XY Jog Pad -->
	<div class="grid grid-cols-3 gap-1.5 mb-3 max-w-[260px] mx-auto">
		<div></div>
		<button
			class="btn-secondary py-4 min-h-[48px] text-center font-medium
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={() => jog('Y', 1)}
			disabled={!isConnected || !!loading}
		>
			<svg class="w-5 h-5 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
			</svg>
			<span class="text-xs mt-0.5 block">Y+</span>
		</button>
		<div></div>
		<button
			class="btn-secondary py-4 min-h-[48px] text-center font-medium
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={() => jog('X', -1)}
			disabled={!isConnected || !!loading}
		>
			<svg class="w-5 h-5 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
			</svg>
			<span class="text-xs mt-0.5 block">X-</span>
		</button>
		<button
			class="btn-secondary py-4 min-h-[48px] text-center text-sm inline-flex items-center justify-center
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={homeAll}
			disabled={!isConnected || !!loading}
		>
			{#if loading === 'home'}
				<span class="animate-spin rounded-full h-4 w-4 border-2 border-surface-400 border-t-white"></span>
			{:else}
				<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
				</svg>
			{/if}
		</button>
		<button
			class="btn-secondary py-4 min-h-[48px] text-center font-medium
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={() => jog('X', 1)}
			disabled={!isConnected || !!loading}
		>
			<svg class="w-5 h-5 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
			</svg>
			<span class="text-xs mt-0.5 block">X+</span>
		</button>
		<div></div>
		<button
			class="btn-secondary py-4 min-h-[48px] text-center font-medium
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={() => jog('Y', -1)}
			disabled={!isConnected || !!loading}
		>
			<svg class="w-5 h-5 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
			</svg>
			<span class="text-xs mt-0.5 block">Y-</span>
		</button>
		<div></div>
	</div>

	<!-- Z controls -->
	<div class="flex gap-2 justify-center mb-4">
		<button
			class="btn-secondary px-6 py-3 min-h-[48px] inline-flex items-center gap-1.5 font-medium
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={() => jog('Z', 1)}
			disabled={!isConnected || !!loading}
		>
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
			</svg>
			Z+
		</button>
		<button
			class="btn-secondary px-6 py-3 min-h-[48px] inline-flex items-center gap-1.5 font-medium
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={() => jog('Z', -1)}
			disabled={!isConnected || !!loading}
		>
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
			</svg>
			Z-
		</button>
	</div>

	<!-- Home axis buttons -->
	<div class="flex gap-1">
		<button
			class="btn-secondary flex-1 text-xs py-2.5 min-h-[40px]
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={() => homeAxis('X')}
			disabled={!isConnected || !!loading}
		>
			Home X
		</button>
		<button
			class="btn-secondary flex-1 text-xs py-2.5 min-h-[40px]
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={() => homeAxis('Y')}
			disabled={!isConnected || !!loading}
		>
			Home Y
		</button>
		<button
			class="btn-secondary flex-1 text-xs py-2.5 min-h-[40px]
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={() => homeAxis('Z')}
			disabled={!isConnected || !!loading}
		>
			Home Z
		</button>
	</div>
</div>
