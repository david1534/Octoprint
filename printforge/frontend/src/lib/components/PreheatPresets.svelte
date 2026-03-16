<script lang="ts">
	import { api } from '$lib/api';
	import { toast } from '$lib/stores/toast';

	interface Preset {
		name: string;
		hotend: number;
		bed: number;
		color: string;
	}

	const defaultPresets: Preset[] = [
		{ name: 'PLA', hotend: 200, bed: 60, color: 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30' },
		{ name: 'PETG', hotend: 230, bed: 80, color: 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30' },
		{ name: 'ABS', hotend: 240, bed: 100, color: 'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30' },
	];

	let loading = $state('');

	function loadCustomPreset(): Preset | null {
		try {
			const raw = localStorage.getItem('printforge:custom-preset');
			if (raw) return JSON.parse(raw);
		} catch { /* ignore */ }
		return null;
	}

	let customPreset = $state<Preset | null>(loadCustomPreset());

	let allPresets = $derived([
		...defaultPresets,
		...(customPreset ? [{ ...customPreset, color: 'bg-purple-500/20 text-purple-400 hover:bg-purple-500/30' }] : [])
	]);

	async function applyPreset(preset: Preset) {
		loading = preset.name;
		try {
			await api.setTemperature(preset.hotend, preset.bed);
			toast.success(`Preheating: ${preset.name} (${preset.hotend}/${preset.bed}°C)`);
		} catch (e: any) {
			toast.error('Failed to set temperature: ' + e.message);
		} finally {
			loading = '';
		}
	}

	async function cooldown() {
		loading = 'cooldown';
		try {
			await api.setTemperature(0, 0);
			toast.info('Cooldown: temperatures set to 0°C');
		} catch (e: any) {
			toast.error('Failed to cool down: ' + e.message);
		} finally {
			loading = '';
		}
	}
</script>

<div class="card">
	<h3 class="text-sm font-semibold text-surface-300 mb-3">Preheat</h3>
	<div class="grid grid-cols-2 gap-2">
		{#each allPresets as preset}
			<button
				class="px-3 py-2.5 rounded-lg text-sm font-medium transition-colors {preset.color}
					   disabled:opacity-50 disabled:cursor-not-allowed
					   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
				onclick={() => applyPreset(preset)}
				disabled={!!loading}
			>
				{#if loading === preset.name}
					<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-current/30 border-t-current inline-block mr-1"></span>
				{/if}
				<span class="font-semibold">{preset.name}</span>
				<span class="block text-xs opacity-70 mt-0.5">{preset.hotend}/{preset.bed}°C</span>
			</button>
		{/each}
		<button
			class="px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
				   bg-surface-700/50 text-surface-400 hover:bg-surface-700 hover:text-surface-200
				   disabled:opacity-50 disabled:cursor-not-allowed
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={cooldown}
			disabled={!!loading}
		>
			{#if loading === 'cooldown'}
				<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-surface-400/30 border-t-surface-400 inline-block mr-1"></span>
			{/if}
			<svg class="w-4 h-4 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M6 18L18 6M6 6l12 12" />
			</svg>
			Cooldown
		</button>
	</div>
</div>
