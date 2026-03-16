<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { tempHistory, type TempPoint } from '../stores/temperature';
	import Chart from 'chart.js/auto';

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

	function updateChart(history: TempPoint[]) {
		if (!chart) return;
		const labels = history.map((p) => {
			const d = new Date(p.time * 1000);
			return `${d.getMinutes()}:${d.getSeconds().toString().padStart(2, '0')}`;
		});
		chart.data.labels = labels;
		chart.data.datasets[0].data = history.map((p) => p.hotendActual);
		chart.data.datasets[1].data = history.map((p) => p.hotendTarget);
		chart.data.datasets[2].data = history.map((p) => p.bedActual);
		chart.data.datasets[3].data = history.map((p) => p.bedTarget);
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
