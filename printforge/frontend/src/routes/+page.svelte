<script lang="ts">
	import { onMount } from 'svelte';
	import CameraFeed from '$lib/components/CameraFeed.svelte';
	import TempChart from '$lib/components/TempChart.svelte';
	import TempGauge from '$lib/components/TempGauge.svelte';
	import PrintProgress from '$lib/components/PrintProgress.svelte';
	import PrintStartDialog from '$lib/components/PrintStartDialog.svelte';
	import FilesDrawer from '$lib/components/FilesDrawer.svelte';
	import AlertPanel from '$lib/components/AlertPanel.svelte';
	import JogControls from '$lib/components/JogControls.svelte';
	import TemperatureControls from '$lib/components/TemperatureControls.svelte';
	import ExtruderControls from '$lib/components/ExtruderControls.svelte';
	import { printerState, isConnected, isPrinting, isPaused, isFinishing } from '$lib/stores/printer';
	import { files, refreshFiles } from '$lib/stores/files';
	import { api } from '$lib/api';
	import { toast } from '$lib/stores/toast';
	import { confirmAction } from '$lib/stores/confirm';
	import { formatDuration } from '$lib/utils';

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

	// Controls active tab
	type ControlTab = 'movement' | 'temperature' | 'extrusion';
	let activeControlTab = $state<ControlTab>('movement');

	// Recent files for quick print
	let recentFiles = $derived($files.slice(0, 3));

	// Files drawer — persisted open/closed preference
	let drawerOpen = $state(false);
	let wasOpenBeforePrint = $state(false);

	$effect(() => {
		// Auto-close drawer when print starts; restore when back to idle
		if (printing || paused || finishing) {
			if (drawerOpen) {
				wasOpenBeforePrint = true;
				drawerOpen = false;
			}
		} else if (wasOpenBeforePrint) {
			drawerOpen = true;
			wasOpenBeforePrint = false;
		}
	});

	$effect(() => {
		// Persist preference — but don't write during a print (auto-close)
		if (printing || paused || finishing) return;
		try {
			localStorage.setItem('printforge:filesDrawerOpen', drawerOpen ? '1' : '0');
		} catch { /* storage disabled */ }
	});

	function toggleDrawer() {
		if (printing || paused || finishing) return; // disabled during print
		drawerOpen = !drawerOpen;
	}

	function closeDrawer() {
		drawerOpen = false;
	}

	function onDashboardKeydown(e: KeyboardEvent) {
		if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'o') {
			// Don't fire if an input/textarea has focus
			const t = e.target as HTMLElement | null;
			const tag = t?.tagName?.toLowerCase();
			if (tag === 'input' || tag === 'textarea' || t?.isContentEditable) return;
			e.preventDefault();
			toggleDrawer();
		}
	}

	// Controls panel ref for scroll-on-click from stat tiles (mobile where panel stacks below)
	let controlsPanelEl = $state<HTMLElement | null>(null);
	function focusControlTab(tab: ControlTab) {
		activeControlTab = tab;
		// Only scroll when the panel is actually below the fold (small screens).
		// On lg+ the panel is sticky beside the camera — scrolling would be disruptive.
		if (typeof window !== 'undefined' && window.matchMedia('(max-width: 1023px)').matches) {
			controlsPanelEl?.scrollIntoView({ behavior: 'smooth', block: 'start' });
		}
	}

	// Track status changes to refresh spool data after print ends
	let lastStatus = $state('');

	onMount(() => {
		if ($isConnected) {
			refreshFiles();
		}
		loadHealth();
		loadActiveSpool();
		loadFilamentWarnings();

		// Restore drawer preference (only honored when idle)
		try {
			const saved = localStorage.getItem('printforge:filesDrawerOpen');
			if (saved === '1') drawerOpen = true;
		} catch { /* storage disabled */ }
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
</script>

<svelte:head>
	<title>PrintForge - Dashboard</title>
</svelte:head>

<svelte:window onkeydown={onDashboardKeydown} />

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

		<!-- Active Alerts (full-width, always first) -->
		<AlertPanel />

		<!-- Print Status Hero (full-width when printing / paused / finishing) -->
		{#if printing || paused || finishing}
			<div class="card bg-gradient-to-r from-surface-900 to-surface-800/50 border-accent/20">
				{#if finishing}
					<div class="flex items-center gap-3 py-2">
						<span class="animate-spin rounded-full h-5 w-5 border-2 border-accent/30 border-t-accent shrink-0"></span>
						<div>
							<h3 class="text-sm font-semibold text-surface-200">Finishing Print</h3>
							<p class="text-xs text-surface-400">Running end G-code, cooling down...</p>
						</div>
					</div>
				{:else}
					<PrintProgress />
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
				{/if}
			</div>
		{/if}

		<!-- Two-column layout: monitoring left | controls right -->
		<!-- On lg+: side-by-side so camera and controls are visible together -->
		<!-- On smaller screens: stacks vertically (camera first, controls below) -->
		<div class="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4 items-start">

			<!-- LEFT: monitoring column — ordered by immediacy -->
			<div class="space-y-3">
				<!-- Camera feed — primary reason for this layout -->
				<CameraFeed />

				<!-- Live metrics: Hotend over Bed in a narrow left column, spool + temperature history on the right.
				     Fan % and position have moved to the top status bar; removing those tiles here gives the
				     chart a wider canvas. Stacks on small screens so nothing gets cramped. -->
				<div class="grid grid-cols-1 md:grid-cols-[240px_1fr] gap-3 items-stretch">
					<!-- Left: Hotend on top, Bed underneath. -->
					<div class="flex flex-col gap-3">
						<TempGauge
							label="Hotend"
							actual={state.hotend.actual}
							target={state.hotend.target}
							color="#f97316"
							title="Adjust hotend temperature"
							onclick={() => focusControlTab('temperature')}
						/>
						<TempGauge
							label="Bed"
							actual={state.bed.actual}
							target={state.bed.target}
							maxTemp={120}
							color="#3b82f6"
							title="Adjust bed temperature"
							onclick={() => focusControlTab('temperature')}
						/>
					</div>

					<!-- Right: spool context + temperature history, stacked. -->
					<div class="flex flex-col gap-3">
						{#if activeSpool}
							{@const remaining = Math.max(0, activeSpool.total_weight_g - activeSpool.used_weight_g)}
							{@const pct = activeSpool.total_weight_g > 0 ? (remaining / activeSpool.total_weight_g) * 100 : 0}
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
									<p class="text-sm font-medium tabular-nums {pct > 20 ? 'text-surface-200' : pct > 5 ? 'text-amber-400' : 'text-red-400'}">
										{remaining.toFixed(0)}g
									</p>
									<div class="w-16 h-1.5 bg-surface-700 rounded-full mt-1 overflow-hidden">
										<div
											class="h-full rounded-full {pct > 20 ? 'bg-accent' : pct > 5 ? 'bg-amber-500' : 'bg-red-500'}"
											style="width: {Math.min(100, pct)}%"
										></div>
									</div>
								</div>
							</div>
						{/if}

						<div class="flex-1 min-h-0">
							<TempChart />
						</div>
					</div>
				</div>

				<!-- Low Filament Warnings — full-width alert below the metrics subgrid -->
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
			</div>

			<!-- RIGHT: controls column — sticky on desktop so controls stay in view while scrolling -->
			<div bind:this={controlsPanelEl} class="space-y-3 lg:sticky lg:top-0">

				<!-- Files quick-access card (idle only) -->
				{#if !printing && !paused && !finishing}
					<div class="card">
						<div class="flex items-center justify-between gap-2">
							<h3 class="text-sm font-semibold text-surface-300 flex items-center gap-2">
								<svg class="w-4 h-4 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
								</svg>
								Files
							</h3>
							<button
								class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors
								       {drawerOpen
								         ? 'bg-accent/15 text-accent hover:bg-accent/20'
								         : 'bg-surface-800 text-surface-300 hover:bg-surface-700 hover:text-surface-100'}
								       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
								onclick={toggleDrawer}
								title="Toggle files drawer (Ctrl+O)"
							>
								<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7" />
								</svg>
								{drawerOpen ? 'Hide' : 'Browse'}
								<span class="hidden lg:inline text-surface-500 font-normal">⌃O</span>
							</button>
						</div>
						{#if recentFiles.length > 0}
							<p class="text-[10px] text-surface-500 uppercase tracking-wider mt-3 mb-1.5">Recent</p>
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
							<p class="text-xs text-surface-500 mt-3">No files uploaded yet</p>
							<a href="/files" class="text-xs text-accent hover:text-accent-hover mt-1 inline-block">Upload files</a>
						{/if}
					</div>
				{/if}

				<!-- Controls Panel: tabbed Movement | Temperature | Extrusion -->
				<div class="space-y-2">
					<!-- Tab bar -->
					<div class="flex gap-1 p-1 bg-surface-800 rounded-xl">
						<button
							class="flex-1 flex flex-col items-center py-2 rounded-lg text-xs font-medium transition-all duration-200
							       {activeControlTab === 'movement'
							         ? 'bg-surface-700 text-surface-100 shadow-sm'
							         : 'text-surface-400 hover:text-surface-200'}
							       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
							onclick={() => activeControlTab = 'movement'}
						>
							<svg class="w-4 h-4 mb-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
							</svg>
							Movement
						</button>
						<button
							class="flex-1 flex flex-col items-center py-2 rounded-lg text-xs font-medium transition-all duration-200
							       {activeControlTab === 'temperature'
							         ? 'bg-surface-700 text-surface-100 shadow-sm'
							         : 'text-surface-400 hover:text-surface-200'}
							       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
							onclick={() => activeControlTab = 'temperature'}
						>
							<svg class="w-4 h-4 mb-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
							</svg>
							Temperature
						</button>
						<button
							class="flex-1 flex flex-col items-center py-2 rounded-lg text-xs font-medium transition-all duration-200
							       {activeControlTab === 'extrusion'
							         ? 'bg-surface-700 text-surface-100 shadow-sm'
							         : 'text-surface-400 hover:text-surface-200'}
							       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
							onclick={() => activeControlTab = 'extrusion'}
						>
							<svg class="w-4 h-4 mb-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
							</svg>
							Extrusion
						</button>
					</div>

					<!-- Tab content — hidden via CSS (not unmounted) to preserve component state -->
					<div class={activeControlTab === 'movement' ? '' : 'hidden'}>
						<JogControls />
					</div>
					<div class={activeControlTab === 'temperature' ? '' : 'hidden'}>
						<TemperatureControls />
					</div>
					<div class={activeControlTab === 'extrusion' ? '' : 'hidden'}>
						<ExtruderControls />
					</div>
				</div>
			</div>
		</div>

		<!-- System Info — full-width footer -->
		{#if health}
			<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
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

<FilesDrawer bind:open={drawerOpen} onclose={closeDrawer} disabled={printing || paused || finishing} />
