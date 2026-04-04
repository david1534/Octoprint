<script lang="ts">
	import { onMount } from 'svelte';

	interface BedMeshData {
		grid: number[][];
		rows: number;
		cols: number;
		min: number;
		max: number;
		mean: number;
		range: number;
		active: boolean;
		timestamp: number;
	}

	let { mesh = null as BedMeshData | null } = $props();

	let canvasEl: HTMLCanvasElement;
	let tooltipText = $state('');
	let tooltipX = $state(0);
	let tooltipY = $state(0);
	let showTooltip = $state(false);

	// Color interpolation: blue (low) -> green (flat) -> red (high)
	function valueToColor(value: number, min: number, max: number): string {
		const range = max - min;
		if (range === 0) return 'rgb(34, 197, 94)'; // green

		// Normalize to 0..1
		const t = (value - min) / range;

		// Blue (0) -> Green (0.5) -> Red (1)
		let r: number, g: number, b: number;
		if (t < 0.5) {
			const s = t * 2; // 0..1 within blue-green
			r = Math.round(59 * s);
			g = Math.round(130 + 67 * s);
			b = Math.round(246 - 180 * s);
		} else {
			const s = (t - 0.5) * 2; // 0..1 within green-red
			r = Math.round(59 + 190 * s);
			g = Math.round(197 - 100 * s);
			b = Math.round(66 - 66 * s);
		}
		return `rgb(${r}, ${g}, ${b})`;
	}

	function drawMesh() {
		if (!canvasEl || !mesh || !mesh.grid.length) return;

		const ctx = canvasEl.getContext('2d');
		if (!ctx) return;

		const { grid, rows, cols, min, max } = mesh;
		const padding = 40;
		const width = canvasEl.width;
		const height = canvasEl.height;
		const cellW = (width - padding * 2) / cols;
		const cellH = (height - padding * 2) / rows;

		// Clear
		ctx.clearRect(0, 0, width, height);

		// Draw cells with interpolated colors
		for (let r = 0; r < rows; r++) {
			for (let c = 0; c < cols; c++) {
				const val = grid[r][c];
				const x = padding + c * cellW;
				const y = padding + r * cellH;

				ctx.fillStyle = valueToColor(val, min, max);
				ctx.fillRect(x, y, cellW, cellH);

				// Cell border
				ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
				ctx.lineWidth = 1;
				ctx.strokeRect(x, y, cellW, cellH);

				// Value text
				ctx.fillStyle = Math.abs(val) > (max - min) * 0.3 ? '#fff' : '#e2e8f0';
				ctx.font = `bold ${Math.min(14, cellW / 4)}px monospace`;
				ctx.textAlign = 'center';
				ctx.textBaseline = 'middle';
				const label = val >= 0 ? `+${val.toFixed(3)}` : val.toFixed(3);
				ctx.fillText(label, x + cellW / 2, y + cellH / 2);
			}
		}

		// Axis labels
		ctx.fillStyle = '#94a3b8';
		ctx.font = '11px sans-serif';
		ctx.textAlign = 'center';

		// Column labels (X axis — front to back)
		for (let c = 0; c < cols; c++) {
			ctx.fillText(String(c), padding + c * cellW + cellW / 2, padding - 10);
		}

		// Row labels (Y axis — left to right)
		ctx.textAlign = 'right';
		for (let r = 0; r < rows; r++) {
			ctx.fillText(String(r), padding - 8, padding + r * cellH + cellH / 2);
		}

		// Axis titles
		ctx.fillStyle = '#64748b';
		ctx.font = '10px sans-serif';
		ctx.textAlign = 'center';
		ctx.fillText('Probe Column', width / 2, 12);
		ctx.save();
		ctx.translate(10, height / 2);
		ctx.rotate(-Math.PI / 2);
		ctx.fillText('Probe Row', 0, 0);
		ctx.restore();

		// Color legend bar
		const legendX = width - padding + 12;
		const legendW = 14;
		const legendH = height - padding * 2;
		const legendY = padding;

		for (let i = 0; i < legendH; i++) {
			const t = 1 - i / legendH; // top = max, bottom = min
			const val = min + t * (max - min);
			ctx.fillStyle = valueToColor(val, min, max);
			ctx.fillRect(legendX, legendY + i, legendW, 1);
		}
		ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
		ctx.strokeRect(legendX, legendY, legendW, legendH);

		// Legend labels
		ctx.fillStyle = '#94a3b8';
		ctx.font = '10px monospace';
		ctx.textAlign = 'left';
		const legendLabelX = legendX + legendW + 4;
		ctx.fillText(`+${max.toFixed(3)}`, legendLabelX, legendY + 4);
		ctx.fillText(`${min >= 0 ? '+' : ''}${min.toFixed(3)}`, legendLabelX, legendY + legendH + 4);
		if (max !== min) {
			const midVal = (min + max) / 2;
			ctx.fillText(`${midVal >= 0 ? '+' : ''}${midVal.toFixed(3)}`, legendLabelX, legendY + legendH / 2 + 3);
		}
	}

	function onCanvasMove(e: MouseEvent) {
		if (!canvasEl || !mesh || !mesh.grid.length) return;

		const rect = canvasEl.getBoundingClientRect();
		const scaleX = canvasEl.width / rect.width;
		const scaleY = canvasEl.height / rect.height;
		const mx = (e.clientX - rect.left) * scaleX;
		const my = (e.clientY - rect.top) * scaleY;

		const padding = 40;
		const cellW = (canvasEl.width - padding * 2) / mesh.cols;
		const cellH = (canvasEl.height - padding * 2) / mesh.rows;

		const col = Math.floor((mx - padding) / cellW);
		const row = Math.floor((my - padding) / cellH);

		if (row >= 0 && row < mesh.rows && col >= 0 && col < mesh.cols) {
			const val = mesh.grid[row][col];
			tooltipText = `Row ${row}, Col ${col}: ${val >= 0 ? '+' : ''}${val.toFixed(4)} mm`;
			tooltipX = e.clientX - rect.left;
			tooltipY = e.clientY - rect.top - 32;
			showTooltip = true;
		} else {
			showTooltip = false;
		}
	}

	function onCanvasLeave() {
		showTooltip = false;
	}

	$effect(() => {
		if (mesh) drawMesh();
	});

	onMount(() => {
		if (mesh) drawMesh();
	});

	let ageLabel = $derived.by(() => {
		if (!mesh?.timestamp) return '';
		const age = Math.floor((Date.now() / 1000) - mesh.timestamp);
		if (age < 60) return `${age}s ago`;
		if (age < 3600) return `${Math.floor(age / 60)}m ago`;
		return `${Math.floor(age / 3600)}h ago`;
	});
</script>

<div class="card">
	<div class="flex items-center justify-between mb-4">
		<div>
			<h3 class="text-sm font-semibold text-surface-200">Bed Mesh Topography</h3>
			{#if mesh}
				<p class="text-xs text-surface-500 mt-0.5">
					{mesh.rows}x{mesh.cols} grid
					{#if mesh.active}
						<span class="text-emerald-400 ml-1">Active</span>
					{:else}
						<span class="text-amber-400 ml-1">Inactive</span>
					{/if}
					{#if ageLabel}
						<span class="text-surface-600 ml-1">{ageLabel}</span>
					{/if}
				</p>
			{/if}
		</div>
	</div>

	{#if mesh && mesh.grid.length > 0}
		<!-- Stats cards -->
		<div class="grid grid-cols-4 gap-2 mb-4">
			<div class="bg-surface-800 rounded-lg px-3 py-2 text-center">
				<span class="text-[10px] text-surface-500 uppercase tracking-wider block">Min</span>
				<span class="text-sm font-mono font-medium text-blue-400">{mesh.min >= 0 ? '+' : ''}{mesh.min.toFixed(3)}</span>
			</div>
			<div class="bg-surface-800 rounded-lg px-3 py-2 text-center">
				<span class="text-[10px] text-surface-500 uppercase tracking-wider block">Max</span>
				<span class="text-sm font-mono font-medium text-red-400">+{mesh.max.toFixed(3)}</span>
			</div>
			<div class="bg-surface-800 rounded-lg px-3 py-2 text-center">
				<span class="text-[10px] text-surface-500 uppercase tracking-wider block">Range</span>
				<span class="text-sm font-mono font-medium text-surface-200">{mesh.range.toFixed(3)}</span>
			</div>
			<div class="bg-surface-800 rounded-lg px-3 py-2 text-center">
				<span class="text-[10px] text-surface-500 uppercase tracking-wider block">Mean</span>
				<span class="text-sm font-mono font-medium text-surface-300">{mesh.mean >= 0 ? '+' : ''}{mesh.mean.toFixed(3)}</span>
			</div>
		</div>

		<!-- Heatmap canvas -->
		<div class="relative bg-surface-800 rounded-lg overflow-hidden">
			<canvas
				bind:this={canvasEl}
				width="520"
				height="420"
				class="w-full"
				style="aspect-ratio: 520/420;"
				onmousemove={onCanvasMove}
				onmouseleave={onCanvasLeave}
			></canvas>
			{#if showTooltip}
				<div
					class="absolute pointer-events-none bg-surface-900/95 border border-surface-600 text-surface-200
						   text-xs font-mono px-2 py-1 rounded shadow-lg whitespace-nowrap z-10"
					style="left: {tooltipX}px; top: {tooltipY}px; transform: translateX(-50%);"
				>
					{tooltipText}
				</div>
			{/if}
		</div>

		<!-- Quality assessment -->
		<div class="mt-3 flex items-center gap-2">
			{#if mesh.range < 0.1}
				<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-emerald-500/20 text-emerald-400">
					<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
					</svg>
					Excellent
				</span>
				<span class="text-xs text-surface-500">Bed is very level ({mesh.range.toFixed(3)}mm variance)</span>
			{:else if mesh.range < 0.3}
				<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-blue-500/20 text-blue-400">
					Good
				</span>
				<span class="text-xs text-surface-500">Within normal range ({mesh.range.toFixed(3)}mm variance)</span>
			{:else if mesh.range < 0.6}
				<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-amber-500/20 text-amber-400">
					Fair
				</span>
				<span class="text-xs text-surface-500">Consider checking bed springs ({mesh.range.toFixed(3)}mm variance)</span>
			{:else}
				<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-red-500/20 text-red-400">
					Poor
				</span>
				<span class="text-xs text-surface-500">Bed needs leveling ({mesh.range.toFixed(3)}mm variance)</span>
			{/if}
		</div>
	{:else}
		<!-- Empty state -->
		<div class="bg-surface-800 rounded-lg py-12 text-center">
			<svg class="w-16 h-16 mx-auto mb-3 text-surface-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" />
			</svg>
			<p class="text-surface-400 text-sm mb-1">No mesh data available</p>
			<p class="text-surface-600 text-xs">Run a bed probe to generate the topography map</p>
		</div>
	{/if}
</div>
