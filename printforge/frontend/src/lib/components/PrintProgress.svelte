<script lang="ts">
	import { printerState } from '../stores/printer';
	import { formatDuration, formatClock } from '../utils';
	import ProgressRing from './ProgressRing.svelte';

	let state = $derived($printerState);
	let p = $derived(state.print);
	let progress = $derived(p.progress);
	let isPrintActive = $derived(state.status === 'printing' || state.status === 'paused');

	let etaTime = $derived(() => {
		if (p.remaining <= 0) return '';
		const eta = new Date(Date.now() + p.remaining * 1000);
		return eta.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
	});
</script>

{#if isPrintActive && p.file}
	<div class="card">
		<div class="flex items-center justify-between mb-3">
			<h3 class="text-sm font-medium text-surface-400">Print Progress</h3>
			{#if state.status === 'paused'}
				<span class="badge-paused">Paused</span>
			{:else}
				<span class="badge-printing">Printing</span>
			{/if}
		</div>

		<p class="text-surface-200 font-medium truncate mb-4">{p.file}</p>

		<!-- Progress ring + stats -->
		<div class="flex items-center gap-6 mb-4">
			<ProgressRing
				progress={progress}
				size={100}
				strokeWidth={7}
				color={state.status === 'paused' ? '#f59e0b' : '#10b981'}
			/>
			<div class="flex-1 space-y-2 text-sm">
				<div class="flex justify-between">
					<span class="text-surface-500">Layer</span>
					<span class="tabular-nums text-surface-200">{p.currentLayer}/{p.totalLayers || '?'}</span>
				</div>
				<div class="flex justify-between">
					<span class="text-surface-500">Z Height</span>
					<span class="tabular-nums text-surface-200">{state.position.z.toFixed(2)} mm</span>
				</div>
				<div class="flex justify-between">
					<span class="text-surface-500">Line</span>
					<span class="tabular-nums text-surface-200">{p.currentLine.toLocaleString()}/{p.totalLines.toLocaleString()}</span>
				</div>
			</div>
		</div>

		<!-- Time stats -->
		<div class="grid grid-cols-2 gap-3 text-sm">
			<div>
				<span class="text-surface-500 text-xs">Elapsed</span>
				<p class="text-surface-200 font-medium tabular-nums">
					{formatDuration(p.elapsed)}
				</p>
			</div>
			<div>
				<span class="text-surface-500 text-xs">Remaining</span>
				<p class="text-surface-200 font-medium tabular-nums">
					{formatDuration(p.remaining)}
					{#if etaTime()}
						<span class="text-surface-500 text-xs ml-1">~{etaTime()}</span>
					{/if}
				</p>
			</div>
		</div>
	</div>
{:else}
	<div class="card">
		<h3 class="text-sm font-medium text-surface-400 mb-3">Print Progress</h3>
		<div class="flex items-center gap-4 py-4">
			<ProgressRing progress={0} size={80} strokeWidth={6} color="#334155" showLabel={false} />
			<p class="text-surface-500 text-sm">No active print</p>
		</div>
	</div>
{/if}
