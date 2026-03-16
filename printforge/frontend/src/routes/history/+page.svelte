<script lang="ts">
	import { onMount } from 'svelte';
	import {
		historyJobs, historyTotal, historyStats, historyLoading,
		fetchHistory, fetchStats, type PrintJob
	} from '$lib/stores/history';
	import { api } from '$lib/api';
	import { toast } from '$lib/stores/toast';
	import { confirmAction } from '$lib/stores/confirm';
	import { formatDuration, formatTimeAgo } from '$lib/utils';
	import LoadingSkeleton from '$lib/components/LoadingSkeleton.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';

	let currentPage = $state(0);
	let statusFilter = $state<string | undefined>(undefined);
	let deleting = $state<number | null>(null);
	const perPage = 20;

	let totalPages = $derived(Math.ceil($historyTotal / perPage));

	const statusTabs = [
		{ label: 'All', value: undefined },
		{ label: 'Completed', value: 'completed' },
		{ label: 'Cancelled', value: 'cancelled' },
		{ label: 'Failed', value: 'failed' },
	];

	onMount(() => {
		fetchHistory(perPage, 0, statusFilter);
		fetchStats();
	});

	function changeFilter(value: string | undefined) {
		statusFilter = value;
		currentPage = 0;
		fetchHistory(perPage, 0, statusFilter);
	}

	function goToPage(page: number) {
		currentPage = page;
		fetchHistory(perPage, page * perPage, statusFilter);
	}

	async function deleteJob(job: PrintJob) {
		const ok = await confirmAction({
			title: 'Delete History Entry',
			message: `Delete the record for "${job.filename}"?`,
			confirmLabel: 'Delete',
			variant: 'danger'
		});
		if (!ok) return;
		deleting = job.id;
		try {
			await api.deleteHistoryEntry(job.id);
			toast.success('History entry deleted');
			fetchHistory(perPage, currentPage * perPage, statusFilter);
			fetchStats();
		} catch (e: any) {
			toast.error('Failed to delete: ' + e.message);
		} finally {
			deleting = null;
		}
	}

	function statusBadge(status: string): string {
		switch (status) {
			case 'completed': return 'badge-printing';
			case 'cancelled': return 'badge-paused';
			case 'failed': return 'badge-error';
			case 'printing': return 'badge-printing';
			default: return 'badge-idle';
		}
	}
</script>

<svelte:head>
	<title>PrintForge - History</title>
</svelte:head>

<h1 class="text-xl font-bold mb-4">Print History</h1>

<!-- Stats cards -->
{#if $historyStats}
	<div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
		<div class="card py-3">
			<span class="text-xs text-surface-500">Total Prints</span>
			<p class="text-2xl font-bold tabular-nums text-surface-100">{$historyStats.total_prints}</p>
		</div>
		<div class="card py-3">
			<span class="text-xs text-surface-500">Success Rate</span>
			<p class="text-2xl font-bold tabular-nums {$historyStats.success_rate >= 0.8 ? 'text-emerald-400' : $historyStats.success_rate >= 0.5 ? 'text-amber-400' : 'text-red-400'}">
				{($historyStats.success_rate * 100).toFixed(0)}%
			</p>
		</div>
		<div class="card py-3">
			<span class="text-xs text-surface-500">Print Hours</span>
			<p class="text-2xl font-bold tabular-nums text-surface-100">{$historyStats.total_hours}h</p>
		</div>
		<div class="card py-3">
			<span class="text-xs text-surface-500">Filament Used</span>
			<p class="text-2xl font-bold tabular-nums text-surface-100">{$historyStats.total_filament_m}m</p>
		</div>
	</div>
{:else}
	<div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
		{#each Array(4) as _}
			<div class="card py-3">
				<LoadingSkeleton lines={2} height="h-3" />
			</div>
		{/each}
	</div>
{/if}

<!-- Status filter tabs -->
<div class="flex gap-1 mb-4 overflow-x-auto">
	{#each statusTabs as tab}
		<button
			class="px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap
				   {statusFilter === tab.value ? 'bg-accent/10 text-accent' : 'text-surface-400 hover:bg-surface-800 hover:text-surface-200'}
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={() => changeFilter(tab.value)}
		>
			{tab.label}
		</button>
	{/each}
</div>

<!-- Job list -->
{#if $historyLoading && $historyJobs.length === 0}
	<div class="space-y-2">
		{#each Array(5) as _}
			<div class="card">
				<LoadingSkeleton lines={2} />
			</div>
		{/each}
	</div>
{:else if $historyJobs.length === 0}
	<EmptyState
		title="No Print History"
		description={statusFilter ? `No ${statusFilter} prints found` : 'Print history will appear here after your first print'}
	>
		{#snippet icon()}
			<svg class="w-8 h-8 text-surface-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
			</svg>
		{/snippet}
	</EmptyState>
{:else}
	<!-- Table (desktop) / Cards (mobile) -->
	<div class="hidden sm:block overflow-x-auto">
		<table class="w-full text-sm">
			<thead>
				<tr class="text-left text-xs text-surface-500 border-b border-surface-700">
					<th class="pb-2 font-medium">File</th>
					<th class="pb-2 font-medium">Date</th>
					<th class="pb-2 font-medium">Duration</th>
					<th class="pb-2 font-medium">Status</th>
					<th class="pb-2 font-medium">Filament</th>
					<th class="pb-2 font-medium w-10"></th>
				</tr>
			</thead>
			<tbody>
				{#each $historyJobs as job}
					<tr class="border-b border-surface-800 hover:bg-surface-800/50 transition-colors">
						<td class="py-3 pr-4">
							<span class="text-surface-200 font-medium truncate block max-w-[200px]">{job.filename}</span>
						</td>
						<td class="py-3 pr-4 text-surface-400 tabular-nums">
							<span title={job.started_at}>{formatTimeAgo(job.started_at)}</span>
						</td>
						<td class="py-3 pr-4 text-surface-400 tabular-nums">
							{formatDuration(job.duration_seconds)}
						</td>
						<td class="py-3 pr-4">
							<span class={statusBadge(job.status)}>{job.status}</span>
						</td>
						<td class="py-3 pr-4 text-surface-400 tabular-nums">
							{job.filament_used_mm ? `${(job.filament_used_mm / 1000).toFixed(1)}m` : '--'}
						</td>
						<td class="py-3">
							<button
								class="btn-icon p-1 text-red-400/50 hover:text-red-400 hover:bg-red-500/10"
								onclick={() => deleteJob(job)}
								disabled={deleting === job.id}
								title="Delete entry"
							>
								{#if deleting === job.id}
									<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-red-400/30 border-t-red-400"></span>
								{:else}
									<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
									</svg>
								{/if}
							</button>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>

	<!-- Mobile cards -->
	<div class="sm:hidden space-y-2">
		{#each $historyJobs as job}
			<div class="card">
				<div class="flex items-start justify-between gap-2">
					<div class="min-w-0">
						<p class="text-surface-200 font-medium truncate">{job.filename}</p>
						<div class="flex gap-3 text-xs text-surface-500 mt-1">
							<span>{formatTimeAgo(job.started_at)}</span>
							<span>{formatDuration(job.duration_seconds)}</span>
							{#if job.filament_used_mm}
								<span>{(job.filament_used_mm / 1000).toFixed(1)}m</span>
							{/if}
						</div>
					</div>
					<span class={statusBadge(job.status)}>{job.status}</span>
				</div>
			</div>
		{/each}
	</div>

	<!-- Pagination -->
	{#if totalPages > 1}
		<div class="flex items-center justify-center gap-2 mt-6">
			<button
				class="btn-secondary text-sm px-3 py-1.5"
				onclick={() => goToPage(currentPage - 1)}
				disabled={currentPage === 0}
			>
				Previous
			</button>
			<span class="text-sm text-surface-400 tabular-nums">
				Page {currentPage + 1} of {totalPages}
			</span>
			<button
				class="btn-secondary text-sm px-3 py-1.5"
				onclick={() => goToPage(currentPage + 1)}
				disabled={currentPage >= totalPages - 1}
			>
				Next
			</button>
		</div>
	{/if}
{/if}
