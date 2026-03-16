<script lang="ts">
	import { fade } from 'svelte/transition';

	// --- Mock Data ---
	const stats = [
		{
			label: 'Total Users',
			value: '12,847',
			change: '+14.2%',
			trend: 'up' as const,
			icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z'
		},
		{
			label: 'Revenue',
			value: '$48,352',
			change: '+8.1%',
			trend: 'up' as const,
			icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z'
		},
		{
			label: 'Orders',
			value: '1,429',
			change: '-3.4%',
			trend: 'down' as const,
			icon: 'M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z'
		},
		{
			label: 'Conversion Rate',
			value: '3.24%',
			change: '+1.7%',
			trend: 'up' as const,
			icon: 'M13 7h8m0 0v8m0-8l-8 8-4-4-6 6'
		}
	];

	const recentOrders = [
		{ id: 'ORD-7291', customer: 'Sarah Mitchell', amount: '$249.00', status: 'completed', date: '2026-03-16' },
		{ id: 'ORD-7290', customer: 'James Wilson', amount: '$1,024.50', status: 'processing', date: '2026-03-16' },
		{ id: 'ORD-7289', customer: 'Emily Chen', amount: '$89.99', status: 'completed', date: '2026-03-15' },
		{ id: 'ORD-7288', customer: 'Michael Torres', amount: '$432.00', status: 'cancelled', date: '2026-03-15' },
		{ id: 'ORD-7287', customer: 'Olivia Park', amount: '$175.25', status: 'pending', date: '2026-03-14' },
		{ id: 'ORD-7286', customer: 'David Kim', amount: '$612.80', status: 'completed', date: '2026-03-14' },
		{ id: 'ORD-7285', customer: 'Rachel Adams', amount: '$58.00', status: 'processing', date: '2026-03-13' }
	];

	// Chart placeholder data points (for the SVG line)
	const chartPoints = [20, 45, 28, 62, 55, 78, 52, 90, 72, 85, 95, 88];

	function statusBadgeClass(status: string): string {
		switch (status) {
			case 'completed': return 'bg-emerald-500/20 text-emerald-400';
			case 'processing': return 'bg-blue-500/20 text-blue-400';
			case 'pending': return 'bg-amber-500/20 text-amber-400';
			case 'cancelled': return 'bg-red-500/20 text-red-400';
			default: return 'bg-surface-500/20 text-surface-400';
		}
	}

	function formatDate(dateStr: string): string {
		const date = new Date(dateStr + 'T00:00:00');
		return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
	}

	// Build SVG polyline path from chart points
	function buildChartPath(points: number[], width: number, height: number): string {
		const maxVal = Math.max(...points);
		const minVal = Math.min(...points);
		const range = maxVal - minVal || 1;
		const padding = 8;
		const usableHeight = height - padding * 2;
		const step = width / (points.length - 1);

		return points
			.map((val, i) => {
				const x = i * step;
				const y = padding + usableHeight - ((val - minVal) / range) * usableHeight;
				return `${x},${y}`;
			})
			.join(' ');
	}

	// Build the filled area path for the chart
	function buildAreaPath(points: number[], width: number, height: number): string {
		const maxVal = Math.max(...points);
		const minVal = Math.min(...points);
		const range = maxVal - minVal || 1;
		const padding = 8;
		const usableHeight = height - padding * 2;
		const step = width / (points.length - 1);

		const linePoints = points.map((val, i) => {
			const x = i * step;
			const y = padding + usableHeight - ((val - minVal) / range) * usableHeight;
			return `${x},${y}`;
		});

		return `M0,${height} L${linePoints.join(' L')} L${width},${height} Z`;
	}
</script>

<svelte:head>
	<title>Dashboard</title>
</svelte:head>

<div in:fade={{ duration: 200 }}>
	<!-- Page Header -->
	<div class="flex items-center justify-between mb-8">
		<div>
			<h1 class="text-2xl font-bold text-surface-100">Dashboard</h1>
			<p class="mt-1 text-sm text-surface-400">Overview of your business metrics.</p>
		</div>
		<button class="btn-primary inline-flex items-center gap-2">
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
			</svg>
			Export
		</button>
	</div>

	<!-- Stat Cards -->
	<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
		{#each stats as stat, i}
			<div class="card group" in:fade={{ duration: 200, delay: i * 50 }}>
				<div class="flex items-start justify-between mb-3">
					<div class="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center">
						<svg class="w-5 h-5 text-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={stat.icon} />
						</svg>
					</div>
					<span
						class="inline-flex items-center gap-1 text-xs font-medium rounded-full px-2 py-0.5
						       {stat.trend === 'up' ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'}"
					>
						<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							{#if stat.trend === 'up'}
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 15l7-7 7 7" />
							{:else}
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7" />
							{/if}
						</svg>
						{stat.change}
					</span>
				</div>
				<p class="text-sm text-surface-400 mb-1">{stat.label}</p>
				<p class="text-2xl font-bold tabular-nums text-surface-100">{stat.value}</p>
			</div>
		{/each}
	</div>

	<!-- Line Chart Placeholder -->
	<div class="card mb-8">
		<div class="flex items-center justify-between mb-6">
			<div>
				<h2 class="text-base font-semibold text-surface-100">Revenue Over Time</h2>
				<p class="mt-0.5 text-sm text-surface-400">Monthly revenue for the past 12 months.</p>
			</div>
			<div class="flex items-center gap-1 bg-surface-800 rounded-lg p-0.5">
				<button class="px-3 py-1.5 text-xs font-medium rounded-md bg-accent/15 text-accent transition-colors">
					12M
				</button>
				<button class="px-3 py-1.5 text-xs font-medium rounded-md text-surface-400 hover:text-surface-200 transition-colors">
					6M
				</button>
				<button class="px-3 py-1.5 text-xs font-medium rounded-md text-surface-400 hover:text-surface-200 transition-colors">
					30D
				</button>
			</div>
		</div>

		<!-- SVG Chart -->
		<div class="w-full h-64 relative">
			<!-- Y-axis labels -->
			<div class="absolute left-0 top-0 bottom-0 flex flex-col justify-between text-xs text-surface-500 tabular-nums pr-3 py-2">
				<span>$100k</span>
				<span>$75k</span>
				<span>$50k</span>
				<span>$25k</span>
				<span>$0</span>
			</div>

			<!-- Chart area -->
			<div class="ml-12 h-full relative">
				<!-- Grid lines -->
				<div class="absolute inset-0 flex flex-col justify-between py-2">
					{#each Array(5) as _, i}
						<div class="border-t border-surface-700/50 w-full"></div>
					{/each}
				</div>

				<!-- SVG Line -->
				<svg class="absolute inset-0 w-full h-full" preserveAspectRatio="none" viewBox="0 0 400 240">
					<defs>
						<linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
							<stop offset="0%" stop-color="rgb(59, 130, 246)" stop-opacity="0.2" />
							<stop offset="100%" stop-color="rgb(59, 130, 246)" stop-opacity="0" />
						</linearGradient>
					</defs>
					<!-- Area fill -->
					<path
						d={buildAreaPath(chartPoints, 400, 240)}
						fill="url(#chartGradient)"
					/>
					<!-- Line -->
					<polyline
						points={buildChartPath(chartPoints, 400, 240)}
						fill="none"
						stroke="rgb(59, 130, 246)"
						stroke-width="2.5"
						stroke-linecap="round"
						stroke-linejoin="round"
					/>
				</svg>

				<!-- X-axis labels -->
				<div class="absolute bottom-0 left-0 right-0 translate-y-full pt-2 flex justify-between text-xs text-surface-500">
					<span>Apr</span>
					<span>May</span>
					<span>Jun</span>
					<span>Jul</span>
					<span>Aug</span>
					<span>Sep</span>
					<span>Oct</span>
					<span>Nov</span>
					<span>Dec</span>
					<span>Jan</span>
					<span>Feb</span>
					<span>Mar</span>
				</div>
			</div>
		</div>

		<!-- Bottom padding for x-axis labels -->
		<div class="h-8"></div>
	</div>

	<!-- Recent Orders Table -->
	<div class="card overflow-hidden">
		<div class="flex items-center justify-between mb-5">
			<div>
				<h2 class="text-base font-semibold text-surface-100">Recent Orders</h2>
				<p class="mt-0.5 text-sm text-surface-400">Latest transactions from your store.</p>
			</div>
			<button class="text-sm font-medium text-accent hover:text-accent-hover transition-colors inline-flex items-center gap-1">
				View all
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
				</svg>
			</button>
		</div>

		<!-- Desktop table -->
		<div class="hidden sm:block -mx-4 -mb-4">
			<table class="w-full">
				<thead>
					<tr class="border-t border-surface-700">
						<th class="text-left text-xs font-medium text-surface-400 uppercase tracking-wide px-4 py-3">
							Order ID
						</th>
						<th class="text-left text-xs font-medium text-surface-400 uppercase tracking-wide px-4 py-3">
							Customer
						</th>
						<th class="text-right text-xs font-medium text-surface-400 uppercase tracking-wide px-4 py-3">
							Amount
						</th>
						<th class="text-left text-xs font-medium text-surface-400 uppercase tracking-wide px-4 py-3">
							Status
						</th>
						<th class="text-right text-xs font-medium text-surface-400 uppercase tracking-wide px-4 py-3">
							Date
						</th>
					</tr>
				</thead>
				<tbody class="divide-y divide-surface-800">
					{#each recentOrders as order}
						<tr class="hover:bg-surface-800/50 transition-colors">
							<td class="px-4 py-3">
								<span class="text-sm font-mono font-medium text-surface-200">{order.id}</span>
							</td>
							<td class="px-4 py-3">
								<span class="text-sm text-surface-200">{order.customer}</span>
							</td>
							<td class="px-4 py-3 text-right">
								<span class="text-sm tabular-nums font-medium text-surface-100">{order.amount}</span>
							</td>
							<td class="px-4 py-3">
								<span class="badge {statusBadgeClass(order.status)} capitalize">
									{order.status}
								</span>
							</td>
							<td class="px-4 py-3 text-right">
								<span class="text-sm text-surface-400 tabular-nums">{formatDate(order.date)}</span>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>

		<!-- Mobile card list -->
		<div class="sm:hidden -mx-4 -mb-4 divide-y divide-surface-800 border-t border-surface-700">
			{#each recentOrders as order}
				<div class="px-4 py-3 flex items-center justify-between gap-3">
					<div class="min-w-0">
						<div class="flex items-center gap-2 mb-0.5">
							<span class="text-sm font-mono font-medium text-surface-200">{order.id}</span>
							<span class="badge {statusBadgeClass(order.status)} capitalize text-[10px]">
								{order.status}
							</span>
						</div>
						<p class="text-sm text-surface-400 truncate">{order.customer}</p>
					</div>
					<div class="text-right shrink-0">
						<p class="text-sm tabular-nums font-medium text-surface-100">{order.amount}</p>
						<p class="text-xs text-surface-500 tabular-nums">{formatDate(order.date)}</p>
					</div>
				</div>
			{/each}
		</div>
	</div>
</div>
