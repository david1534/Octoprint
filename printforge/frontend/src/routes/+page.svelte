<script lang="ts">
	import { onMount } from 'svelte';
	import CameraFeed from '$lib/components/CameraFeed.svelte';
	import TempChart from '$lib/components/TempChart.svelte';
	import TempGauge from '$lib/components/TempGauge.svelte';
	import PrintProgress from '$lib/components/PrintProgress.svelte';
	import PreheatPresets from '$lib/components/PreheatPresets.svelte';
	import PrintStartDialog from '$lib/components/PrintStartDialog.svelte';
	import AlertPanel from '$lib/components/AlertPanel.svelte';
	import { printerState, isConnected, isPrinting, isPaused, isFinishing } from '$lib/stores/printer';
	import { files, refreshFiles } from '$lib/stores/files';
	import { api } from '$lib/api';
	import { toast } from '$lib/stores/toast';
	import { confirmAction } from '$lib/stores/confirm';
	import { formatFileSize, formatDuration } from '$lib/utils';

	let state = $derived($printerState);
	let connected = $derived($isConnected);
	let printing = $derived($isPrinting);
	let paused = $derived($isPaused);
	let finishing = $derived($isFinishing);
	let loading = $state('');
	let health = $state<any>(null);
	let activeSpool = $state<any>(null);
	let filamentWarnings = $state<any[]>([]);

	// Print start dialog
	let printDialogOpen = $state(false);
	let printDialogFilename = $state('');

	// Recent files for quick print
	let recentFiles = $derived(
		$files.slice(0, 3)
	);

	// Track status changes to refresh spool data after print ends
	let lastStatus = $state('');

	onMount(() => {
		if ($isConnected) {
			refreshFiles();
		}
		loadHealth();
		loadActiveSpool();
		loadFilamentWarnings();
	});

	// Refresh spool data when print finishes (filament deducted)
	$effect(() => {
		const currentStatus = state.status;
		if (lastStatus && lastStatus !== currentStatus) {
			const wasPrinting = lastStatus === 'printing' || lastStatus === 'finishing' || lastStatus === 'paused';
			const nowDone = currentStatus === 'idle' || currentStatus === 'error';
			if (wasPrinting && nowDone) {
				loadActiveSpool();
				loadFilamentWarnings();
			}
		}
		lastStatus = currentStatus;
	});

	async function loadActiveSpool() {
		try {
			const data = await api.getActiveSpool();
			activeSpool = data.spool;
		} catch { /* not critical */ }
	}

	async function loadFilamentWarnings() {
		try {
			const data = await api.getLowFilamentWarnings();
			filamentWarnings = data.warnings || [];
		} catch { /* not critical */ }
	}

	async function loadHealth() {
		try {
			health = await api.getHealth();
		} catch { /* not critical */ }
	}

	async function pausePrint() {
		loading = 'pause';
		try {
			await api.pausePrint();
			toast.info('Print paused');
		} catch (e: any) {
			toast.error('Failed to pause: ' + e.message);
		} finally {
			loading = '';
		}
	}

	async function resumePrint() {
		loading = 'resume';
		try {
			await api.resumePrint();
			toast.success('Print resumed');
		} catch (e: any) {
			toast.error('Failed to resume: ' + e.message);
		} finally {
			loading = '';
		}
	}

	async function cancelPrint() {
		const ok = await confirmAction({
			title: 'Cancel Print',
			message: `Cancel printing "${state.print.file}"? This cannot be undone.`,
			confirmLabel: 'Cancel Print',
			variant: 'danger'
		});
		if (!ok) return;
		loading = 'cancel';
		try {
			await api.cancelPrint();
			toast.success('Print cancelled');
		} catch (e: any) {
			toast.error('Failed to cancel: ' + e.message);
		} finally {
			loading = '';
		}
	}

	function quickPrint(filename: string) {
		printDialogFilename = filename;
		printDialogOpen = true;
	}

	async function onPrintConfirm(spoolId: number | null) {
		const filename = printDialogFilename;
		printDialogOpen = false;
		printDialogFilename = '';
		loading = 'qprint:' + filename;
		try {
			await api.startPrint(filename, spoolId ?? undefined);
			toast.success('Print started: ' + filename);
		} catch (e: any) {
			toast.error('Failed to start: ' + e.message);
		} finally {
			loading = '';
		}
	}

	function onPrintCancel() {
		printDialogOpen = false;
		printDialogFilename = '';
	}

	async function quickHome() {
		loading = 'home';
		try {
			await api.home();
			toast.info('Homing all axes');
		} catch (e: any) {
			toast.error('Home failed: ' + e.message);
		} finally {
			loading = '';
		}
	}

	async function quickJogZ(distance: number) {
		loading = 'jog';
		try {
			await api.jog(0, 0, distance);
		} catch (e: any) {
			toast.error('Jog failed: ' + e.message);
		} finally {
			loading = '';
		}
	}
</script>

<svelte:head>
	<title>PrintForge - Dashboard</title>
</svelte:head>

{#if !connected}
	<!-- Disconnected state -->
	<div class="max-w-md mx-auto mt-20 text-center fade-in">
		<div class="w-16 h-16 bg-accent/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
			<div class="w-10 h-10 bg-accent rounded-xl flex items-center justify-center">
				<span class="text-white font-bold">PF</span>
			</div>
		</div>
		<h1 class="text-2xl font-bold mb-2">PrintForge</h1>
		<p class="text-surface-400 mb-6">Connect to your printer to get started</p>
		<a href="/settings" class="btn-primary inline-block">Go to Settings</a>
	</div>
{:else}
	<div class="space-y-4 fade-in">
		<!-- Finishing state banner -->
		{#if finishing}
			<div class="card bg-gradient-to-r from-surface-900 to-surface-800/50 border-accent/20">
				<div class="flex items-center gap-3 py-2">
					<span class="animate-spin rounded-full h-5 w-5 border-2 border-accent/30 border-t-accent"></span>
					<div>
						<h3 class="text-sm font-semibold text-surface-200">Finishing Print</h3>
						<p class="text-xs text-surface-400">Running end G-code, cooling down...</p>
					</div>
				</div>
			</div>
		{/if}

		<!-- Print Status Hero (when printing/paused) -->
		{#if printing || paused}
			<div class="card bg-gradient-to-r from-surface-900 to-surface-800/50 border-accent/20">
				<PrintProgress />
				<!-- Print controls -->
				<div class="flex gap-2 mt-4">
					{#if printing}
						<button
							class="btn-secondary flex-1 inline-flex items-center justify-center gap-2"
							onclick={pausePrint}
							disabled={!!loading}
						>
							{#if loading === 'pause'}
								<span class="animate-spin rounded-full h-4 w-4 border-2 border-surface-400 border-t-white"></span>
							{:else}
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
								</svg>
							{/if}
							Pause
						</button>
					{:else}
						<button
							class="btn-success flex-1 inline-flex items-center justify-center gap-2"
							onclick={resumePrint}
							disabled={!!loading}
						>
							{#if loading === 'resume'}
								<span class="animate-spin rounded-full h-4 w-4 border-2 border-emerald-800 border-t-white"></span>
							{:else}
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
								</svg>
							{/if}
							Resume
						</button>
					{/if}
					<button
						class="btn-danger flex-1 inline-flex items-center justify-center gap-2"
						onclick={cancelPrint}
						disabled={!!loading}
					>
						{#if loading === 'cancel'}
							<span class="animate-spin rounded-full h-4 w-4 border-2 border-red-800 border-t-white"></span>
						{:else}
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
							</svg>
						{/if}
						Cancel
					</button>
				</div>
			</div>
		{/if}

		<!-- Active Alerts -->
		<AlertPanel />

		<!-- Camera + Temperature Row -->
		<div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
			<CameraFeed />
			<TempChart />
		</div>

		<!-- Temperature Gauges -->
		<div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
			<TempGauge label="Hotend" actual={state.hotend.actual} target={state.hotend.target} color="#f97316" />
			<TempGauge label="Bed" actual={state.bed.actual} target={state.bed.target} maxTemp={120} color="#3b82f6" />
			<div class="card flex items-center gap-3">
				<div class="w-8 h-8 bg-surface-800 rounded-lg flex items-center justify-center shrink-0">
					<svg class="w-4 h-4 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
					</svg>
				</div>
				<div>
					<span class="text-xs text-surface-500">Fan</span>
					<p class="text-sm font-medium tabular-nums text-surface-200">{Math.round(state.fan_speed / 2.55)}%</p>
				</div>
			</div>
			<div class="card flex items-center gap-3">
				<div class="w-8 h-8 bg-surface-800 rounded-lg flex items-center justify-center shrink-0">
					<svg class="w-4 h-4 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
					</svg>
				</div>
				<div>
					<span class="text-xs text-surface-500">Position</span>
					<p class="text-xs font-medium tabular-nums text-surface-200">
						X:{state.position.x.toFixed(1)} Y:{state.position.y.toFixed(1)} Z:{state.position.z.toFixed(1)}
					</p>
				</div>
			</div>
		</div>

		<!-- Active Spool -->
		{#if activeSpool}
			<div class="card flex items-center gap-3 py-3">
				<div class="w-8 h-8 rounded-full shrink-0 border border-surface-600" style="background-color: {activeSpool.color}"></div>
				<div class="flex-1 min-w-0">
					<div class="flex items-center gap-2">
						<span class="text-xs text-surface-500">Active Spool</span>
						<span class="text-xs px-1.5 py-0.5 rounded bg-surface-700 text-surface-400">{activeSpool.material}</span>
					</div>
					<p class="text-sm font-medium text-surface-200 truncate">{activeSpool.name}</p>
				</div>
				<div class="text-right shrink-0">
					{#if activeSpool}
						{@const remaining = Math.max(0, activeSpool.total_weight_g - activeSpool.used_weight_g)}
						{@const pct = activeSpool.total_weight_g > 0 ? (remaining / activeSpool.total_weight_g) * 100 : 0}
						<p class="text-sm font-medium tabular-nums {pct > 20 ? 'text-surface-200' : pct > 5 ? 'text-amber-400' : 'text-red-400'}">
							{remaining.toFixed(0)}g
						</p>
						<div class="w-16 h-1.5 bg-surface-700 rounded-full mt-1 overflow-hidden">
							<div
								class="h-full rounded-full {pct > 20 ? 'bg-accent' : pct > 5 ? 'bg-amber-500' : 'bg-red-500'}"
								style="width: {Math.min(100, pct)}%"
							></div>
						</div>
					{/if}
				</div>
			</div>
		{/if}

		<!-- Low Filament Warnings -->
		{#if filamentWarnings.length > 0}
			<div class="bg-amber-500/10 border border-amber-500/20 rounded-xl px-4 py-3">
				<div class="flex items-start gap-2">
					<svg class="w-5 h-5 text-amber-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
					</svg>
					<div>
						<p class="text-sm font-medium text-amber-300 mb-1">Low Filament Warning</p>
						<div class="space-y-1">
							{#each filamentWarnings as w}
								<div class="flex items-center gap-2 text-xs text-amber-300/80">
									<div class="w-3 h-3 rounded-full shrink-0 border border-amber-500/30" style="background-color: {w.color}"></div>
									<span class="font-medium">{w.name}</span>
									<span class="text-amber-400/60">({w.material})</span>
									<span class="tabular-nums">{w.remaining_g}g remaining</span>
								</div>
							{/each}
						</div>
					</div>
				</div>
			</div>
		{/if}

		<!-- Quick Actions Row (when idle) -->
		{#if !printing && !paused && !finishing}
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
				<!-- Quick Print -->
				<div class="card">
					<h3 class="text-sm font-semibold text-surface-300 mb-3 flex items-center gap-2">
						<svg class="w-4 h-4 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
						Quick Print
					</h3>
					{#if recentFiles.length > 0}
						<div class="space-y-1.5">
							{#each recentFiles as file}
								<button
									class="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg bg-surface-800/50 hover:bg-surface-800
										   text-left transition-colors text-sm group
										   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50
										   disabled:opacity-50 disabled:cursor-not-allowed"
									onclick={() => quickPrint(file.filename)}
									disabled={!!loading}
								>
									<svg class="w-4 h-4 text-surface-500 group-hover:text-accent shrink-0 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
									</svg>
									<span class="truncate text-surface-300 group-hover:text-surface-100">{file.filename}</span>
									{#if file.estimatedTime}
										<span class="text-xs text-surface-600 ml-auto shrink-0">{formatDuration(file.estimatedTime)}</span>
									{/if}
								</button>
							{/each}
						</div>
					{:else}
						<p class="text-xs text-surface-500">No files uploaded yet</p>
						<a href="/files" class="text-xs text-accent hover:text-accent-hover mt-1 inline-block">Upload files</a>
					{/if}
				</div>

				<!-- Preheat Presets -->
				<PreheatPresets />

				<!-- Quick Move -->
				<div class="card">
					<h3 class="text-sm font-semibold text-surface-300 mb-3 flex items-center gap-2">
						<svg class="w-4 h-4 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
						</svg>
						Quick Move
					</h3>
					<div class="grid grid-cols-2 gap-2">
						<button
							class="btn-secondary text-sm py-2.5 inline-flex items-center justify-center gap-1.5"
							onclick={quickHome}
							disabled={!!loading}
						>
							{#if loading === 'home'}
								<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-surface-400 border-t-white"></span>
							{:else}
								<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
								</svg>
							{/if}
							Home All
						</button>
						<button
							class="btn-secondary text-sm py-2.5 inline-flex items-center justify-center gap-1.5"
							onclick={() => api.home('Z')}
							disabled={!!loading}
						>
							Home Z
						</button>
						<button
							class="btn-secondary text-sm py-2.5 inline-flex items-center justify-center gap-1.5"
							onclick={() => quickJogZ(10)}
							disabled={!!loading}
						>
							Z +10
						</button>
						<button
							class="btn-secondary text-sm py-2.5 inline-flex items-center justify-center gap-1.5"
							onclick={() => quickJogZ(-10)}
							disabled={!!loading}
						>
							Z -10
						</button>
					</div>
				</div>
			</div>
		{/if}

		<!-- System Info Footer -->
		{#if health}
			<div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
				<div class="card flex items-center gap-3 py-3">
					<div class="w-8 h-8 bg-surface-800 rounded-lg flex items-center justify-center shrink-0">
						<svg class="w-4 h-4 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
						</svg>
					</div>
					<div>
						<span class="text-xs text-surface-500">CPU Temp</span>
						<p class="text-sm font-medium tabular-nums text-surface-200">{health.cpuTemp?.toFixed(1) || '0'}°C</p>
					</div>
				</div>
				<div class="card flex items-center gap-3 py-3">
					<div class="w-8 h-8 bg-surface-800 rounded-lg flex items-center justify-center shrink-0">
						<svg class="w-4 h-4 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13 10V3L4 14h7v7l9-11h-7z" />
						</svg>
					</div>
					<div>
						<span class="text-xs text-surface-500">CPU Load</span>
						<p class="text-sm font-medium tabular-nums text-surface-200">{health.cpuUsage?.toFixed(1) || '0'}%</p>
					</div>
				</div>
				<div class="card flex items-center gap-3 py-3">
					<div class="w-8 h-8 bg-surface-800 rounded-lg flex items-center justify-center shrink-0">
						<svg class="w-4 h-4 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 4v16m8-8H4" />
						</svg>
					</div>
					<div>
						<span class="text-xs text-surface-500">Memory</span>
						<p class="text-sm font-medium tabular-nums text-surface-200">{health.memory?.percent || '0'}%</p>
					</div>
				</div>
				<div class="card flex items-center gap-3 py-3">
					<div class="w-8 h-8 bg-surface-800 rounded-lg flex items-center justify-center shrink-0">
						<svg class="w-4 h-4 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
					</div>
					<div>
						<span class="text-xs text-surface-500">Uptime</span>
						<p class="text-sm font-medium tabular-nums text-surface-200">
							{Math.floor((health.uptime || 0) / 3600)}h {Math.floor(((health.uptime || 0) % 3600) / 60)}m
						</p>
					</div>
				</div>
			</div>
		{/if}
	</div>
{/if}


<PrintStartDialog
	bind:open={printDialogOpen}
	filename={printDialogFilename}
	onconfirm={onPrintConfirm}
	oncancel={onPrintCancel}
/>