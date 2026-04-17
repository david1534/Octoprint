<script lang="ts">
	import { onMount } from 'svelte';
	import { fly, fade } from 'svelte/transition';
	import { page } from '$app/stores';
	import '../app.css';
	import { wsManager } from '$lib/websocket';
	import { initPrinterStore, printerState, wsConnected, statusBadge, isPrinting, isPaused } from '$lib/stores/printer';
	import { initTempHistory } from '$lib/stores/temperature';
	import { initTerminalStore } from '$lib/stores/terminal';
	import { initErrorStore } from '$lib/stores/errors';
	import { api } from '$lib/api';
	import ToastContainer from '$lib/components/ToastContainer.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import CommandPalette from '$lib/components/CommandPalette.svelte';
	import { toast } from '$lib/stores/toast';
	import { confirmAction } from '$lib/stores/confirm';
	import { formatTemp, formatDuration } from '$lib/utils';

	let { children } = $props();

	let state = $derived($printerState);
	let connected = $derived($wsConnected);
	let printing = $derived($isPrinting);
	let paused = $derived($isPaused);
	let currentPath = $derived($page.url.pathname);

	const navItems = [
		{ path: '/', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
		{ path: '/files', label: 'Files', icon: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z' },
		{ path: '/timelapse', label: 'Timelapse', icon: 'M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z' },
		{ path: '/mesh', label: 'Mesh', icon: 'M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z' },
		{ path: '/history', label: 'History', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
		{ path: '/terminal', label: 'Terminal', icon: 'M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' },
		{ path: '/settings', label: 'Settings', icon: 'M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4' }
	];

	// Mobile nav splits primary 3 into bottom tabs + "More" sheet for the rest.
	const mobilePrimaryPaths = ['/', '/files', '/timelapse'];
	const mobilePrimary = $derived(navItems.filter(n => mobilePrimaryPaths.includes(n.path)));
	const mobileMore = $derived(navItems.filter(n => !mobilePrimaryPaths.includes(n.path)));
	const moreIcon = 'M4 6h16M4 12h16M4 18h7';
	let moreSheetOpen = $state(false);
	// The "More" tab highlights when the current route is in the more group
	let isMoreActive = $derived(mobileMore.some(n => currentPath.startsWith(n.path)));
	function openMoreSheet() { moreSheetOpen = true; }
	function closeMoreSheet() { moreSheetOpen = false; }

	async function emergencyStop() {
		try {
			await api.emergencyStop();
			toast.warning('Emergency stop triggered');
		} catch (e) {
			toast.error('Emergency stop failed');
		}
	}

	// Command palette (Ctrl+K / ⌘K)
	let paletteOpen = $state(false);
	function closePalette() { paletteOpen = false; }

	function handleKeydown(e: KeyboardEvent) {
		const ctrl = e.ctrlKey || e.metaKey;
		const key = e.key.toLowerCase();

		// Ctrl+E for emergency stop — always wins
		if (ctrl && key === 'e') {
			e.preventDefault();
			emergencyStop();
			return;
		}

		// Ctrl+K toggles command palette
		if (ctrl && key === 'k') {
			e.preventDefault();
			paletteOpen = !paletteOpen;
			return;
		}

		// Escape closes the mobile More sheet
		if (key === 'escape' && moreSheetOpen) {
			moreSheetOpen = false;
		}
	}

	// Environment banner — shown when running on staging or in mock-serial mode
	// so you can never mistake the test environment for the real one.
	let envBadge = $state<{ environment: string; mockSerial: boolean } | null>(null);
	const isNonProduction = $derived(
		!!envBadge && (envBadge.environment !== 'production' || envBadge.mockSerial)
	);
	const isStaging = $derived(!!envBadge && envBadge.environment === 'staging');
	let promoting = $state(false);

	async function promoteToProduction(force = false) {
		const ok = await confirmAction({
			title: force ? 'Force promote to production?' : 'Promote staging to production?',
			message: force
				? "Production state couldn't be verified or a print is in progress. Promoting now will RESTART the printer service and interrupt any active print. Continue anyway?"
				: "This copies staging's code onto production and restarts the printer service. It's blocked automatically if a print is in progress.",
			confirmLabel: force ? 'Force promote' : 'Promote',
			variant: force ? 'danger' : 'primary'
		});
		if (!ok) return;

		promoting = true;
		try {
			const res = await api.promoteStagingToProduction(force);
			toast.success(`Promoted to production (was: ${res?.productionStatusBefore ?? 'unknown'})`);
		} catch (e: any) {
			const msg = String(e?.message ?? e ?? 'unknown');
			// 409 from backend = print in progress or unverifiable state — offer force
			if (msg.includes('force=true') || msg.includes('409')) {
				promoting = false;
				await promoteToProduction(true);
				return;
			}
			toast.error(`Promote failed: ${msg}`);
		} finally {
			promoting = false;
		}
	}

	onMount(() => {
		initPrinterStore();
		initTempHistory();
		initTerminalStore();
		initErrorStore();
		wsManager.connect();

		// Best-effort health fetch — a 401/network error just means no banner
		api.getHealth()
			.then((h: any) => {
				if (h && typeof h === 'object') {
					envBadge = { environment: h.environment ?? 'production', mockSerial: !!h.mockSerial };
				}
			})
			.catch(() => { /* no banner */ });

		return () => wsManager.disconnect();
	});
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="flex h-screen overflow-hidden">
	<!-- Sidebar (desktop) — icon-only rail -->
	<nav class="hidden md:flex flex-col w-14 bg-surface-900 border-r border-surface-700 shrink-0">
		<!-- Nav items -->
		<div class="flex-1 py-2 space-y-0.5">
			{#each navItems as item}
				{@const isActive = item.path === '/' ? currentPath === '/' : currentPath.startsWith(item.path)}
				<a
					href={item.path}
					title={item.label}
					aria-label={item.label}
					class="flex items-center justify-center py-2.5 mx-2 rounded-lg transition-all duration-200 relative group
						   {isActive
							? 'bg-accent/10 text-accent'
							: 'text-surface-400 hover:bg-surface-800 hover:text-surface-200'}"
				>
					<div class="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 rounded-r bg-accent nav-indicator
								{isActive ? 'h-5 opacity-100' : 'h-0 opacity-0'}"></div>
					<svg class="w-5 h-5 shrink-0 transition-transform duration-200 {isActive ? '' : 'group-hover:scale-110'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={item.icon} />
					</svg>
				</a>
			{/each}
		</div>
	</nav>

	<!-- Main content -->
	<div class="flex-1 flex flex-col overflow-hidden">
		<!-- Environment banner — staging or mock-serial mode -->
		{#if isNonProduction && envBadge}
			<div class="bg-amber-500/15 border-b-2 border-amber-500/60 px-4 py-1.5 flex items-center justify-center gap-3 text-xs font-semibold text-amber-300 shrink-0 tracking-wide uppercase">
				<svg class="w-4 h-4 shrink-0" fill="currentColor" viewBox="0 0 20 20">
					<path fill-rule="evenodd" d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
				</svg>
				<span>
					{envBadge.environment === 'staging' ? 'Staging environment' : envBadge.environment}
					{#if envBadge.mockSerial}· simulated printer (no real hardware connected){/if}
				</span>
				{#if isStaging}
					<button
						onclick={() => promoteToProduction(false)}
						disabled={promoting}
						class="ml-2 px-2.5 py-0.5 rounded-md bg-amber-500/30 hover:bg-amber-500/50 disabled:opacity-50 disabled:cursor-not-allowed text-amber-100 border border-amber-400/50 transition-colors normal-case tracking-normal font-medium"
					>
						{promoting ? 'Promoting…' : 'Promote to production →'}
					</button>
				{/if}
			</div>
		{/if}

		<!-- Top bar -->
		<header class="h-14 bg-surface-900 border-b border-surface-700 flex items-center justify-between px-4 shrink-0">
			<div class="flex items-center gap-3 min-w-0">
				<!-- Logo -->
				<div class="flex items-center gap-2 shrink-0">
					<div class="w-7 h-7 bg-accent rounded-lg flex items-center justify-center">
						<span class="text-white font-bold text-xs">PF</span>
					</div>
					<span class="hidden sm:block font-semibold text-surface-100 text-sm">PrintForge</span>
				</div>

				<!-- Connection dot + status badge -->
				<div class="flex items-center gap-2 shrink-0">
					<div
						class="w-2 h-2 rounded-full transition-all duration-500 {connected ? 'bg-emerald-400 glow-green' : 'bg-red-400 glow-red animate-pulse'}"
						title={connected ? 'Connected' : 'Reconnecting...'}
						aria-label={connected ? 'Connected' : 'Reconnecting'}
					></div>
					<span class="transition-colors duration-300 {$statusBadge}">{state.status}</span>
				</div>

				<!-- Live temps (when connected) -->
				{#if state.status !== 'disconnected'}
					<div class="hidden sm:flex items-center gap-3 text-xs tabular-nums">
						<span class="text-orange-400" title="Hotend temperature">
							<svg class="w-3.5 h-3.5 inline-block mr-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
							</svg>
							{formatTemp(state.hotend.actual, state.hotend.target)}
						</span>
						<span class="text-blue-400" title="Bed temperature">
							<svg class="w-3.5 h-3.5 inline-block mr-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6z" />
							</svg>
							{formatTemp(state.bed.actual, state.bed.target)}
						</span>
					</div>
				{/if}

				<!-- Compact print progress pill (shown on every page when printing) -->
				{#if printing || paused}
					<div
						class="hidden md:flex items-center gap-1.5 text-xs shrink-0 pl-2 border-l border-surface-700"
						title={state.print.file || ''}
					>
						<span class="text-accent font-medium tabular-nums">{Math.round(state.print.progress)}%</span>
						{#if state.print.remaining > 0}
							<span class="text-surface-500 tabular-nums">· ~{formatDuration(state.print.remaining)}</span>
						{/if}
					</div>
				{/if}

				{#if !connected}
					<span class="text-xs text-amber-400 hidden sm:inline animate-pulse">reconnecting...</span>
				{/if}
			</div>

		<!-- Right side: E-STOP -->
		<button
			class="bg-red-600 hover:bg-red-700 text-white font-bold px-4 py-1.5 rounded-lg
				   transition-all duration-200 uppercase text-sm tracking-wide shrink-0
				   ring-2 ring-red-500/30 hover:ring-red-500/50 hover:shadow-lg hover:shadow-red-500/20
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400
				   active:scale-95"
			onclick={emergencyStop}
			title="Emergency Stop (Ctrl+E)"
		>
			E-STOP
		</button>
		</header>

		<!-- WebSocket disconnection banner -->
		{#if !connected}
			<div class="bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 flex items-center gap-2 text-sm text-amber-400 shrink-0">
				<svg class="w-4 h-4 shrink-0 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
				</svg>
				<span>Connection lost. Attempting to reconnect...</span>
			</div>
		{/if}

		<!-- Page content -->
		<main class="flex-1 overflow-y-auto p-4 lg:p-6 pb-20 md:pb-6">
			<div class="page-transition">
				{@render children()}
			</div>
		</main>
	</div>

	<!-- Bottom nav (mobile) — 3 primary tabs + More -->
	<nav class="md:hidden fixed bottom-0 left-0 right-0 bg-surface-900/95 backdrop-blur-lg border-t border-surface-700/80 flex z-50 safe-bottom">
		{#each mobilePrimary as item}
			{@const isActive = item.path === '/' ? currentPath === '/' : currentPath.startsWith(item.path)}
			<a
				href={item.path}
				class="flex-1 flex flex-col items-center py-2 text-xs transition-all duration-200 relative
					   {isActive ? 'text-accent' : 'text-surface-500 active:text-surface-300'}"
			>
				<div class="absolute top-0 left-1/2 -translate-x-1/2 h-0.5 rounded-b bg-accent nav-indicator
							{isActive ? 'w-5 opacity-100' : 'w-0 opacity-0'}"></div>
				<svg class="w-5 h-5 mb-0.5 transition-transform duration-200 {isActive ? 'scale-110' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={item.icon} />
				</svg>
				{item.label}
			</a>
		{/each}
		<button
			type="button"
			onclick={openMoreSheet}
			aria-label="More pages"
			aria-expanded={moreSheetOpen}
			class="flex-1 flex flex-col items-center py-2 text-xs transition-all duration-200 relative
			       {isMoreActive || moreSheetOpen ? 'text-accent' : 'text-surface-500 active:text-surface-300'}
			       focus-visible:outline-none focus-visible:bg-surface-800/60"
		>
			<div class="absolute top-0 left-1/2 -translate-x-1/2 h-0.5 rounded-b bg-accent nav-indicator
						{isMoreActive || moreSheetOpen ? 'w-5 opacity-100' : 'w-0 opacity-0'}"></div>
			<svg class="w-5 h-5 mb-0.5 transition-transform duration-200 {isMoreActive || moreSheetOpen ? 'scale-110' : ''}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={moreIcon} />
			</svg>
			More
		</button>
	</nav>
</div>

<!-- Mobile "More" bottom sheet -->
{#if moreSheetOpen}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="md:hidden fixed inset-0 z-[60] bg-black/50 backdrop-blur-sm"
		onclick={closeMoreSheet}
		transition:fade={{ duration: 150 }}
	></div>
	<div
		class="md:hidden fixed left-0 right-0 bottom-0 z-[70] bg-surface-900 border-t border-surface-700 rounded-t-2xl
		       shadow-2xl safe-bottom"
		transition:fly={{ y: 300, duration: 200 }}
		role="dialog"
		aria-label="More pages"
	>
		<div class="flex items-center justify-between px-4 py-3 border-b border-surface-700">
			<div class="flex items-center gap-2">
				<div class="w-8 h-1 bg-surface-700 rounded-full"></div>
			</div>
			<span class="text-sm font-medium text-surface-300">More</span>
			<button
				class="p-1.5 rounded hover:bg-surface-800 text-surface-400"
				onclick={closeMoreSheet}
				aria-label="Close"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
				</svg>
			</button>
		</div>
		<div class="grid grid-cols-2 gap-2 p-3">
			{#each mobileMore as item}
				{@const isActive = currentPath.startsWith(item.path)}
				<a
					href={item.path}
					onclick={closeMoreSheet}
					class="flex items-center gap-3 px-4 py-3 rounded-xl transition-colors
					       {isActive ? 'bg-accent/10 text-accent' : 'bg-surface-800/60 text-surface-200 hover:bg-surface-800'}"
				>
					<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={item.icon} />
					</svg>
					<span class="text-sm font-medium">{item.label}</span>
				</a>
			{/each}
		</div>
	</div>
{/if}

<ToastContainer />
<ConfirmDialog />
<CommandPalette bind:open={paletteOpen} onclose={closePalette} {navItems} />
