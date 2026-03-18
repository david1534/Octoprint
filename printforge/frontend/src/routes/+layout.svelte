<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import '../app.css';
	import { wsManager } from '$lib/websocket';
	import { initPrinterStore, printerState, wsConnected, statusBadge, isPrinting, isPaused } from '$lib/stores/printer';
	import { initTempHistory } from '$lib/stores/temperature';
	import { initTerminalStore } from '$lib/stores/terminal';
	import { api } from '$lib/api';
	import ToastContainer from '$lib/components/ToastContainer.svelte';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import { toast } from '$lib/stores/toast';
	import { formatTemp, formatDuration } from '$lib/utils';

	let { children } = $props();

	let state = $derived($printerState);
	let connected = $derived($wsConnected);
	let printing = $derived($isPrinting);
	let paused = $derived($isPaused);
	let currentPath = $derived($page.url.pathname);

	const navItems = [
		{ path: '/', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
		{ path: '/control', label: 'Control', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
		{ path: '/files', label: 'Files', icon: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z' },
		{ path: '/timelapse', label: 'Timelapse', icon: 'M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z' },
		{ path: '/mesh', label: 'Mesh', icon: 'M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z' },
		{ path: '/history', label: 'History', icon: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' },
		{ path: '/terminal', label: 'Terminal', icon: 'M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' },
		{ path: '/settings', label: 'Settings', icon: 'M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4' }
	];

	async function emergencyStop() {
		try {
			await api.emergencyStop();
			toast.warning('Emergency stop triggered');
		} catch (e) {
			toast.error('Emergency stop failed');
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		// Ctrl+E or Ctrl+Shift+E for emergency stop
		if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'e') {
			e.preventDefault();
			emergencyStop();
		}
	}

	onMount(() => {
		initPrinterStore();
		initTempHistory();
		initTerminalStore();
		wsManager.connect();

		return () => wsManager.disconnect();
	});
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="flex h-screen overflow-hidden">
	<!-- Sidebar (desktop) -->
	<nav class="hidden md:flex flex-col w-16 lg:w-48 bg-surface-900 border-r border-surface-700 shrink-0">
		<!-- Logo -->
		<div class="p-3 lg:p-4 border-b border-surface-700">
			<div class="flex items-center gap-2">
				<div class="w-8 h-8 bg-accent rounded-lg flex items-center justify-center">
					<span class="text-white font-bold text-sm">PF</span>
				</div>
				<span class="hidden lg:block font-semibold text-surface-100">PrintForge</span>
			</div>
		</div>

		<!-- Nav items -->
		<div class="flex-1 py-2 space-y-0.5">
			{#each navItems as item}
				{@const isActive = item.path === '/' ? currentPath === '/' : currentPath.startsWith(item.path)}
				<a
					href={item.path}
					class="flex items-center gap-3 px-3 py-2.5 mx-2 rounded-lg transition-all duration-200 relative group
						   {isActive
							? 'bg-accent/10 text-accent'
							: 'text-surface-400 hover:bg-surface-800 hover:text-surface-200'}"
				>
					<div class="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 rounded-r bg-accent nav-indicator
								{isActive ? 'h-5 opacity-100' : 'h-0 opacity-0'}"></div>
					<svg class="w-5 h-5 shrink-0 transition-transform duration-200 {isActive ? '' : 'group-hover:scale-110'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={item.icon} />
					</svg>
					<span class="hidden lg:block text-sm">{item.label}</span>
				</a>
			{/each}
		</div>

		<!-- Connection status -->
		<div class="p-3 border-t border-surface-700">
			<div class="flex items-center gap-2">
				<div class="w-2 h-2 rounded-full transition-all duration-500 {connected ? 'bg-emerald-400 glow-green' : 'bg-red-400 glow-red animate-pulse'}"></div>
				<span class="hidden lg:block text-xs transition-colors duration-300 {connected ? 'text-surface-500' : 'text-red-400/70'}">
					{connected ? 'Connected' : 'Reconnecting...'}
				</span>
			</div>
		</div>
	</nav>

	<!-- Main content -->
	<div class="flex-1 flex flex-col overflow-hidden">
		<!-- Top bar -->
		<header class="h-14 bg-surface-900 border-b border-surface-700 flex items-center justify-between px-4 shrink-0">
			<div class="flex items-center gap-3 min-w-0">
				<!-- Mobile logo -->
				<div class="md:hidden flex items-center gap-2 shrink-0">
					<div class="w-7 h-7 bg-accent rounded-lg flex items-center justify-center">
						<span class="text-white font-bold text-xs">PF</span>
					</div>
				</div>

				<!-- Status badge -->
				<span class="transition-colors duration-300 {$statusBadge} shrink-0">{state.status}</span>

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

				<!-- Print progress (inline, when printing) -->
				{#if printing || paused}
					<div class="hidden md:flex items-center gap-2 text-xs text-surface-300 min-w-0">
						<span class="text-surface-600">|</span>
						<span class="truncate max-w-[120px] lg:max-w-[200px]" title={state.print.file || ''}>
							{state.print.file || 'Unknown'}
						</span>
						<span class="text-accent font-medium tabular-nums">{Math.round(state.print.progress)}%</span>
						{#if state.print.remaining > 0}
							<span class="text-surface-500 tabular-nums" title="Estimated time remaining">
								~{formatDuration(state.print.remaining)}
							</span>
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

	<!-- Bottom nav (mobile) -->
	<nav class="md:hidden fixed bottom-0 left-0 right-0 bg-surface-900/95 backdrop-blur-lg border-t border-surface-700/80 flex z-50 safe-bottom">
		{#each navItems as item}
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
	</nav>
</div>

<ToastContainer />
<ConfirmDialog />
