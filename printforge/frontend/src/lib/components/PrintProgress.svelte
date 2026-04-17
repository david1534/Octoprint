<script lang="ts">
	import { printerState } from '../stores/printer';
	import { formatDuration, formatClock } from '../utils';
	import ProgressRing from './ProgressRing.svelte';

	let state = $derived($printerState);
	let p = $derived(state.print);
	let progress = $derived(p.progress);
	let isPrintActive = $derived(state.status === 'printing' || state.status === 'paused');

	let etaTime = $derived.by(() => {
		if (p.remaining <= 0) return '';
		const eta = new Date(Date.now() + p.remaining * 1000);
		return eta.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
	});

	// Absolute clock time when the print started — useful for "when did I kick this off?"
	let startedClock = $derived.by(() => {
		if (p.elapsed <= 0) return '';
		const started = new Date(Date.now() - p.elapsed * 1000);
		return started.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
	});

	// Rolling average layer time — lets you predict when the next layer starts.
	let avgLayerSec = $derived(p.currentLayer > 0 && p.elapsed > 0 ? p.elapsed / p.currentLayer : 0);

	// Live line throughput — a "pace" indicator. Drops signal tricky sections (infill, bridges, retractions).
	let linesPerSec = $derived(p.elapsed > 0 && p.currentLine > 0 ? p.currentLine / p.elapsed : 0);
</script>

{#if isPrintActive && p.file}
	<div class="flex items-center gap-6 w-full">
		<!-- Progress ring -->
		<div class="shrink-0">
			<ProgressRing
				progress={progress}
				size={110}
				strokeWidth={7}
				color={state.status === 'paused' ? '#f59e0b' : '#10b981'}
			/>
		</div>

		<!-- Info section -->
		<div class="flex-1 min-w-0">
			<!-- Header: filename + badge -->
			<div class="flex items-center gap-3 mb-3">
				<p class="text-surface-100 font-semibold truncate text-base">{p.file}</p>
				{#if state.status === 'paused'}
					<span class="badge-paused shrink-0">Paused</span>
				{:else}
					<span class="badge-printing shrink-0">Printing</span>
				{/if}
			</div>

			<!-- Stats grid -->
			<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-x-6 gap-y-2">
				<div>
					<span class="text-xs text-surface-500">Layer</span>
					<p class="text-sm font-medium tabular-nums text-surface-200">{p.currentLayer}/{p.totalLayers || '?'}</p>
				</div>
				<div>
					<span class="text-xs text-surface-500">Z Height</span>
					<p class="text-sm font-medium tabular-nums text-surface-200">{state.position.z.toFixed(2)} mm</p>
				</div>
				<div>
					<span class="text-xs text-surface-500">Line</span>
					<p class="text-sm font-medium tabular-nums text-surface-200">{p.currentLine.toLocaleString()}/{p.totalLines.toLocaleString()}</p>
				</div>
				<div>
					<span class="text-xs text-surface-500">Elapsed</span>
					<p class="text-sm font-medium tabular-nums text-surface-200">{formatDuration(p.elapsed)}</p>
				</div>
				<div>
					<span class="text-xs text-surface-500">Remaining</span>
					<p class="text-sm font-medium tabular-nums text-surface-200">
						{formatDuration(p.remaining)}
						{#if etaTime}
							<span class="text-surface-500 text-xs">~{etaTime}</span>
						{/if}
					</p>
				</div>
			</div>

			<!-- Secondary telemetry strip — derived stats with no backend cost, bullet-separated, muted to stay secondary. -->
			{#if startedClock || avgLayerSec > 0 || linesPerSec > 0}
				<div class="mt-3 pt-3 border-t border-surface-700/50 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-surface-500">
					{#if startedClock}
						<span>Started <span class="text-surface-300 tabular-nums">{startedClock}</span></span>
					{/if}
					{#if avgLayerSec > 0}
						<span class="text-surface-700">·</span>
						<span>Avg layer <span class="text-surface-300 tabular-nums">{formatClock(avgLayerSec)}</span></span>
					{/if}
					{#if linesPerSec > 0}
						<span class="text-surface-700">·</span>
						<span><span class="text-surface-300 tabular-nums">{linesPerSec.toFixed(1)}</span> lines/s</span>
					{/if}
				</div>
			{/if}
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
