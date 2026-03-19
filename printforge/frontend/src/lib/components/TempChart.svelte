<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { tempHistory, type TempPoint } from '../stores/temperature';
	// Tree-shaken Chart.js imports (~30KB gzipped savings vs chart.js/auto)
	import {
		Chart,
		LineController,
		LineElement,
		PointElement,
		LinearScale,
		CategoryScale,
		Legend,
		Filler,
		Tooltip
	} from 'chart.js';

	Chart.register(
		LineController,
		LineElement,
		PointElement,
		LinearScale,
		CategoryScale,
		Legend,
		Filler,
		Tooltip
	);

	let canvas: HTMLCanvasElement;
	let chart: Chart | null = null;
	let unsubscribe: (() => void) | null = null;

	function createChart() {
		if (!canvas) return;
		chart = new Chart(canvas, {
			type: 'line',
			data: {
				labels: [],
				datasets: [
					{
						label: 'Hotend',
						data: [],
						borderColor: '#f97316',
						backgroundColor: 'rgba(249, 115, 22, 0.1)',
						borderWidth: 2,
						pointRadius: 0,
						tension: 0.3,
						fill: true
					},
					{
						label: 'Hotend Target',
						data: [],
						borderColor: '#f97316',
						borderWidth: 1,
						borderDash: [5, 5],
						pointRadius: 0,
						tension: 0
					},
					{
						label: 'Bed',
						data: [],
						borderColor: '#3b82f6',
						backgroundColor: 'rgba(59, 130, 246, 0.1)',
						borderWidth: 2,
						pointRadius: 0,
						tension: 0.3,
						fill: true
					},
					{
						label: 'Bed Target',
						data: [],
						borderColor: '#3b82f6',
						borderWidth: 1,
						borderDash: [5, 5],
						pointRadius: 0,
						tension: 0
					}
				]
			},
			options: {
				responsive: true,
				maintainAspectRatio: false,
				animation: { duration: 0 },
				interaction: { mode: 'nearest', intersect: false },
				plugins: {
					legend: {
						position: 'top',
						labels: {
							color: '#94a3b8',
							usePointStyle: true,
							pointStyle: 'line',
							font: { size: 11 }
						}
					}
				},
				scales: {
					x: {
						display: false
					},
					y: {
						beginAtZero: true,
						grid: { color: 'rgba(148, 163, 184, 0.1)' },
						ticks: { color: '#94a3b8', font: { size: 11 } }
					}
				}
			}
		});
	}

	let lastHistoryLen = 0;

	function updateChart(history: TempPoint[]) {
		if (!chart) return;
		const len = history.length;

		if (len === 0) {
			// Reset chart on clear
			chart.data.labels = [];
			for (const ds of chart.data.datasets) ds.data = [];
			lastHistoryLen = 0;
			chart.update('none');
			return;
		}

		// Incremental update: only process new points instead of
		// rebuilding all 4 arrays (O(1) amortized vs O(n) per tick)
		if (len > lastHistoryLen && lastHistoryLen > 0) {
			const newPoints = history.slice(lastHistoryLen);
			const labels = chart.data.labels as string[];
			for (const p of newPoints) {
				const d = new Date(p.time * 1000);
				labels.push(`${d.getMinutes()}:${d.getSeconds().toString().padStart(2, '0')}`);
				(chart.data.datasets[0].data as number[]).push(p.hotendActual);
				(chart.data.datasets[1].data as number[]).push(p.hotendTarget);
				(chart.data.datasets[2].data as number[]).push(p.bedActual);
				(chart.data.datasets[3].data as number[]).push(p.bedTarget);
			}
			// Trim to match history length (handles the rolling window)
			const excess = labels.length - len;
			if (excess > 0) {
				labels.splice(0, excess);
				for (const ds of chart.data.datasets) (ds.data as number[]).splice(0, excess);
			}
		} else {
			// Full rebuild on first load or history reset
			chart.data.labels = history.map((p) => {
				const d = new Date(p.time * 1000);
				return `${d.getMinutes()}:${d.getSeconds().toString().padStart(2, '0')}`;
			});
			chart.data.datasets[0].data = history.map((p) => p.hotendActual);
			chart.data.datasets[1].data = history.map((p) => p.hotendTarget);
			chart.data.datasets[2].data = history.map((p) => p.bedActual);
			chart.data.datasets[3].data = history.map((p) => p.bedTarget);
		}

		lastHistoryLen = len;
		chart.update('none');
	}

	onMount(() => {
		createChart();
		unsubscribe = tempHistory.subscribe(updateChart);
	});

	onDestroy(() => {
		if (unsubscribe) unsubscribe();
		if (chart) chart.destroy();
	});
</script>

<div class="card h-full">
	<h3 class="text-sm font-medium text-surface-400 mb-2">Temperature</h3>
	<div class="h-48">
		<canvas bind:this={canvas}></canvas>
	</div>
</div>
