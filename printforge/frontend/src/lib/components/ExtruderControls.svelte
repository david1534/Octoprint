<script lang="ts">
	import { api } from '../api';
	import { printerState } from '../stores/printer';
	import { toast } from '../stores/toast';

	let length = $state(10);
	let feedrate = $state(300);
	let fanSpeed = $state(0);
	let loading = $state('');
	let isConnected = $derived($printerState.status !== 'disconnected');
	let hotendTemp = $derived($printerState.hotend.actual);
	let isColdExtrude = $derived(hotendTemp < 180);

	const quickLengths = [1, 5, 10, 50];

	async function doExtrude() {
		if (isColdExtrude) {
			toast.warning('Hotend is below 180°C - heat up before extruding');
			return;
		}
		loading = 'extrude';
		try {
			await api.extrude(length, feedrate);
		} catch (e: any) {
			toast.error('Extrude failed: ' + e.message);
		} finally {
			loading = '';
		}
	}

	async function doRetract() {
		if (isColdExtrude) {
			toast.warning('Hotend is below 180°C - heat up before retracting');
			return;
		}
		loading = 'retract';
		try {
			await api.extrude(-length, feedrate);
		} catch (e: any) {
			toast.error('Retract failed: ' + e.message);
		} finally {
			loading = '';
		}
	}

	async function setFan() {
		loading = 'fan';
		try {
			await api.setFan(Math.round(fanSpeed * 2.55));
			toast.info(`Fan: ${fanSpeed}%`);
		} catch (e: any) {
			toast.error('Failed to set fan: ' + e.message);
		} finally {
			loading = '';
		}
	}

	async function motorsOff() {
		loading = 'motors';
		try {
			await api.motorsOff();
			toast.info('Motors disabled');
		} catch (e: any) {
			toast.error('Failed to disable motors: ' + e.message);
		} finally {
			loading = '';
		}
	}
</script>

<div class="card">
	<h3 class="text-sm font-medium text-surface-400 mb-3">Extrusion & Fan</h3>

	<!-- Cold extrude warning -->
	{#if isColdExtrude && isConnected}
		<div class="bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2 mb-3 text-xs text-amber-400 flex items-center gap-2">
			<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
			</svg>
			Hotend is {hotendTemp.toFixed(0)}°C - heat to 180°C+ before extruding
		</div>
	{/if}

	<!-- Quick length selector -->
	<div class="mb-3">
		<span class="text-xs text-surface-500 mb-1 block">Length</span>
		<div class="flex gap-1">
			{#each quickLengths as ql}
				<button
					class="flex-1 py-2.5 min-h-[40px] rounded-lg text-sm font-medium transition-colors
						   {length === ql ? 'bg-accent text-white' : 'bg-surface-800 text-surface-400 hover:bg-surface-700'}
						   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
					onclick={() => length = ql}
				>
					{ql}mm
				</button>
			{/each}
		</div>
	</div>

	<!-- Custom length + feedrate -->
	<div class="flex gap-2 mb-3">
		<div class="flex-1">
			<label class="text-xs text-surface-500 mb-1 block">Custom (mm)</label>
			<input type="number" class="input w-full" bind:value={length} min="1" max="200" />
		</div>
		<div class="flex-1">
			<label class="text-xs text-surface-500 mb-1 block">Speed (mm/min)</label>
			<input type="number" class="input w-full" bind:value={feedrate} min="60" max="1200" />
		</div>
	</div>

	<div class="flex gap-2 mb-4">
		<button
			class="btn-primary flex-1 min-h-[44px] inline-flex items-center justify-center gap-2
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={doExtrude}
			disabled={!isConnected || !!loading}
		>
			{#if loading === 'extrude'}
				<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white/30 border-t-white"></span>
			{:else}
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
				</svg>
			{/if}
			Extrude
		</button>
		<button
			class="btn-secondary flex-1 min-h-[44px] inline-flex items-center justify-center gap-2
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={doRetract}
			disabled={!isConnected || !!loading}
		>
			{#if loading === 'retract'}
				<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-surface-400 border-t-white"></span>
			{:else}
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 10l7-7m0 0l7 7m-7-7v18" />
				</svg>
			{/if}
			Retract
		</button>
	</div>

	<!-- Fan speed -->
	<div class="mb-3">
		<div class="flex justify-between text-xs mb-1">
			<span class="text-surface-500">Fan Speed</span>
			<span class="text-surface-300 tabular-nums">{fanSpeed}%</span>
		</div>
		<input
			type="range"
			class="w-full accent-accent"
			min="0" max="100"
			bind:value={fanSpeed}
			onchange={setFan}
			disabled={!isConnected || !!loading}
		/>
	</div>

	<button
		class="btn-secondary w-full text-sm min-h-[40px] inline-flex items-center justify-center gap-2
			   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
		onclick={motorsOff}
		disabled={!isConnected || !!loading}
	>
		{#if loading === 'motors'}
			<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-surface-400 border-t-white"></span>
		{:else}
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
			</svg>
		{/if}
		Motors Off
	</button>
</div>
