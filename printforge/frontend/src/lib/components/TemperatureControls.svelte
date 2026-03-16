<script lang="ts">
	import { api } from '../api';
	import { printerState } from '../stores/printer';
	import { toast } from '../stores/toast';

	let hotendInput = $state('');
	let bedInput = $state('');
	let loading = $state('');
	let isConnected = $derived($printerState.status !== 'disconnected');
	let hotend = $derived($printerState.hotend);
	let bed = $derived($printerState.bed);

	const presets = [
		{ name: 'PLA', hotend: 200, bed: 60 },
		{ name: 'PETG', hotend: 230, bed: 80 },
		{ name: 'ABS', hotend: 240, bed: 100 },
		{ name: 'TPU', hotend: 230, bed: 50 }
	];

	async function setHotend() {
		const temp = parseFloat(hotendInput);
		if (isNaN(temp)) return;
		loading = 'hotend';
		try {
			await api.setTemperature(temp);
			toast.info(`Hotend target: ${temp}°C`);
		} catch (e: any) {
			toast.error('Failed to set hotend: ' + e.message);
		} finally {
			loading = '';
		}
	}

	async function setBed() {
		const temp = parseFloat(bedInput);
		if (isNaN(temp)) return;
		loading = 'bed';
		try {
			await api.setTemperature(undefined, temp);
			toast.info(`Bed target: ${temp}°C`);
		} catch (e: any) {
			toast.error('Failed to set bed: ' + e.message);
		} finally {
			loading = '';
		}
	}

	async function applyPreset(preset: typeof presets[0]) {
		loading = 'preset:' + preset.name;
		try {
			await api.setTemperature(preset.hotend, preset.bed);
			hotendInput = String(preset.hotend);
			bedInput = String(preset.bed);
			toast.info(`${preset.name} preset applied`);
		} catch (e: any) {
			toast.error('Failed to apply preset: ' + e.message);
		} finally {
			loading = '';
		}
	}

	async function coolDown() {
		loading = 'cooldown';
		try {
			await api.setTemperature(0, 0);
			hotendInput = '';
			bedInput = '';
			toast.info('Cooling down...');
		} catch (e: any) {
			toast.error('Failed to cool down: ' + e.message);
		} finally {
			loading = '';
		}
	}
</script>

<div class="card">
	<h3 class="text-sm font-medium text-surface-400 mb-3">Temperature</h3>

	<!-- Current temps -->
	<div class="flex gap-4 mb-4 p-2.5 bg-surface-800/50 rounded-lg">
		<div class="flex-1 text-center">
			<span class="text-xs text-surface-500">Hotend</span>
			<p class="text-lg font-semibold tabular-nums text-orange-400">
				{hotend.actual.toFixed(0)}°C
				{#if hotend.target > 0}
					<span class="text-xs text-surface-500 font-normal">/ {hotend.target}°C</span>
				{/if}
			</p>
		</div>
		<div class="w-px bg-surface-700"></div>
		<div class="flex-1 text-center">
			<span class="text-xs text-surface-500">Bed</span>
			<p class="text-lg font-semibold tabular-nums text-blue-400">
				{bed.actual.toFixed(0)}°C
				{#if bed.target > 0}
					<span class="text-xs text-surface-500 font-normal">/ {bed.target}°C</span>
				{/if}
			</p>
		</div>
	</div>

	<!-- Presets -->
	<div class="flex gap-1 mb-4">
		{#each presets as preset}
			<button
				class="btn-secondary flex-1 text-xs py-2.5 min-h-[40px] inline-flex items-center justify-center
					   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
				onclick={() => applyPreset(preset)}
				disabled={!isConnected || !!loading}
			>
				{#if loading === 'preset:' + preset.name}
					<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-surface-400 border-t-white"></span>
				{:else}
					{preset.name}
				{/if}
			</button>
		{/each}
	</div>

	<!-- Hotend -->
	<div class="mb-2">
		<label class="text-xs text-surface-500 mb-1 block">Hotend (°C)</label>
		<div class="flex gap-1">
			<input
				type="number"
				class="input flex-1"
				placeholder="200"
				bind:value={hotendInput}
				disabled={!isConnected || !!loading}
			/>
			<button
				class="btn-primary text-sm px-4 min-h-[40px] inline-flex items-center gap-1.5
					   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
				onclick={setHotend}
				disabled={!isConnected || !!loading}
			>
				{#if loading === 'hotend'}
					<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white/30 border-t-white"></span>
				{/if}
				Set
			</button>
		</div>
	</div>

	<!-- Bed -->
	<div class="mb-3">
		<label class="text-xs text-surface-500 mb-1 block">Bed (°C)</label>
		<div class="flex gap-1">
			<input
				type="number"
				class="input flex-1"
				placeholder="60"
				bind:value={bedInput}
				disabled={!isConnected || !!loading}
			/>
			<button
				class="btn-primary text-sm px-4 min-h-[40px] inline-flex items-center gap-1.5
					   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
				onclick={setBed}
				disabled={!isConnected || !!loading}
			>
				{#if loading === 'bed'}
					<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white/30 border-t-white"></span>
				{/if}
				Set
			</button>
		</div>
	</div>

	<button
		class="btn-secondary w-full text-sm min-h-[40px] inline-flex items-center justify-center gap-2
			   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
		onclick={coolDown}
		disabled={!isConnected || !!loading}
	>
		{#if loading === 'cooldown'}
			<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-surface-400 border-t-white"></span>
		{:else}
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M6 18L18 6M6 6l12 12" />
			</svg>
		{/if}
		Cooldown (All Off)
	</button>
</div>
