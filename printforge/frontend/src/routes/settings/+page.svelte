<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { printerState, isConnected } from '$lib/stores/printer';
	import { toast } from '$lib/stores/toast';

	let ports = $state<string[]>([]);
	let selectedPort = $state('/dev/ttyUSB0');
	let baudrate = $state(115200);
	let connecting = $state(false);
	let disconnecting = $state(false);
	let error = $state('');
	let connected = $derived($isConnected);
	let health = $state<any>(null);
	let notificationsEnabled = $state(false);
	let notificationPermission = $state(typeof Notification !== 'undefined' ? Notification.permission : 'default');

	// Settings tab
	let activeTab = $state<'connection' | 'notifications' | 'display' | 'system'>('connection');

	// Display settings (localStorage)
	let defaultJogDistance = $state(10);
	let tempUnit = $state<'C' | 'F'>('C');

	// Preheat presets management
	interface Preset {
		name: string;
		hotend: number;
		bed: number;
	}
	let customPresets = $state<Preset[]>([]);
	let newPresetName = $state('');
	let newPresetHotend = $state(200);
	let newPresetBed = $state(60);

	const baudRates = [115200, 250000, 57600, 38400, 19200, 9600];

	const tabs = [
		{ id: 'connection' as const, label: 'Connection', icon: 'M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1' },
		{ id: 'notifications' as const, label: 'Notifications', icon: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9' },
		{ id: 'display' as const, label: 'Display', icon: 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' },
		{ id: 'system' as const, label: 'System', icon: 'M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z' },
	];

	onMount(async () => {
		notificationsEnabled = localStorage.getItem('printforge:notifications') === 'true';
		defaultJogDistance = parseInt(localStorage.getItem('printforge:jogDistance') || '10');
		tempUnit = (localStorage.getItem('printforge:tempUnit') as 'C' | 'F') || 'C';
		loadCustomPresets();
		await loadPorts();
		await loadHealth();
	});

	function loadCustomPresets() {
		try {
			const raw = localStorage.getItem('printforge:custom-presets');
			if (raw) customPresets = JSON.parse(raw);
		} catch { /* ignore */ }
	}

	function saveCustomPresets() {
		localStorage.setItem('printforge:custom-presets', JSON.stringify(customPresets));
	}

	function addPreset() {
		if (!newPresetName.trim()) return;
		customPresets = [...customPresets, { name: newPresetName.trim(), hotend: newPresetHotend, bed: newPresetBed }];
		saveCustomPresets();
		newPresetName = '';
		newPresetHotend = 200;
		newPresetBed = 60;
		toast.success('Preset added');
	}

	function removePreset(index: number) {
		customPresets = customPresets.filter((_, i) => i !== index);
		saveCustomPresets();
		toast.info('Preset removed');
	}

	async function loadPorts() {
		try {
			const data = await api.getSerialPorts();
			ports = data.ports || [];
			if (ports.length > 0 && !ports.includes(selectedPort)) {
				selectedPort = ports[0];
			}
		} catch (e) {
			ports = ['/dev/ttyUSB0', '/dev/ttyACM0'];
		}
	}

	async function loadHealth() {
		try {
			health = await api.getHealth();
		} catch (e) {
			// Ignore
		}
	}

	async function connectPrinter() {
		connecting = true;
		error = '';
		try {
			await api.connect(selectedPort, baudrate);
			toast.success('Printer connected');
		} catch (e: any) {
			error = e.message || 'Connection failed';
			toast.error('Connection failed: ' + (e.message || 'Unknown error'));
		} finally {
			connecting = false;
		}
	}

	async function disconnectPrinter() {
		disconnecting = true;
		try {
			await api.disconnect();
			toast.info('Printer disconnected');
		} catch (e: any) {
			toast.error('Disconnect failed: ' + e.message);
		} finally {
			disconnecting = false;
		}
	}

	async function toggleNotifications() {
		if (!notificationsEnabled) {
			if (typeof Notification === 'undefined') {
				toast.warning('Notifications not supported in this browser');
				return;
			}
			const perm = await Notification.requestPermission();
			notificationPermission = perm;
			if (perm === 'granted') {
				notificationsEnabled = true;
				localStorage.setItem('printforge:notifications', 'true');
				toast.success('Notifications enabled');
			} else {
				toast.warning('Notification permission denied');
			}
		} else {
			notificationsEnabled = false;
			localStorage.setItem('printforge:notifications', 'false');
			toast.info('Notifications disabled');
		}
	}

	function testNotification() {
		if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
			new Notification('PrintForge', {
				body: 'Test notification - everything is working!',
				icon: '/favicon.png'
			});
		}
	}

	function saveJogDistance() {
		localStorage.setItem('printforge:jogDistance', String(defaultJogDistance));
		toast.info(`Default jog distance: ${defaultJogDistance}mm`);
	}

	function saveTempUnit() {
		localStorage.setItem('printforge:tempUnit', tempUnit);
		toast.info(`Temperature unit: °${tempUnit}`);
	}
</script>

<svelte:head>
	<title>PrintForge - Settings</title>
</svelte:head>

<h1 class="text-xl font-bold mb-6">Settings</h1>

<div class="flex gap-6 max-w-4xl">
	<!-- Sidebar tabs -->
	<nav class="hidden sm:block w-48 shrink-0">
		<div class="space-y-1 sticky top-4">
			{#each tabs as tab}
				<button
					class="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm text-left transition-colors
						   {activeTab === tab.id
							? 'bg-accent/10 text-accent'
							: 'text-surface-400 hover:bg-surface-800 hover:text-surface-200'}
						   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
					onclick={() => activeTab = tab.id}
				>
					<svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={tab.icon} />
					</svg>
					{tab.label}
				</button>
			{/each}
		</div>
	</nav>

	<!-- Mobile tab bar -->
	<div class="sm:hidden fixed top-14 left-0 right-0 bg-surface-900 border-b border-surface-700 z-40 flex overflow-x-auto px-4 gap-1">
		{#each tabs as tab}
			<button
				class="px-3 py-2.5 text-xs font-medium whitespace-nowrap transition-colors border-b-2
					   {activeTab === tab.id
						? 'text-accent border-accent'
						: 'text-surface-400 border-transparent hover:text-surface-200'}"
				onclick={() => activeTab = tab.id}
			>
				{tab.label}
			</button>
		{/each}
	</div>

	<!-- Content -->
	<div class="flex-1 space-y-6 sm:pt-0 pt-12">
		<!-- Connection Tab -->
		{#if activeTab === 'connection'}
			<div class="card">
				<h2 class="text-lg font-semibold mb-4">Printer Connection</h2>

				<div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
					<div>
						<label class="block text-sm text-surface-400 mb-1">Serial Port</label>
						<select class="input w-full" bind:value={selectedPort} disabled={connected}>
							{#each ports as port}
								<option value={port}>{port}</option>
							{/each}
						</select>
					</div>
					<div>
						<label class="block text-sm text-surface-400 mb-1">Baud Rate</label>
						<select class="input w-full" bind:value={baudrate} disabled={connected}>
							{#each baudRates as rate}
								<option value={rate}>{rate.toLocaleString()}</option>
							{/each}
						</select>
					</div>
				</div>

				{#if error}
					<div class="bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2 mb-4 text-sm text-red-400">
						{error}
					</div>
				{/if}

				{#if connected}
					<div class="flex items-center gap-3">
						<div class="flex items-center gap-2">
							<div class="w-2 h-2 rounded-full bg-emerald-400"></div>
							<span class="text-sm text-surface-300">Connected to {$printerState.port}</span>
						</div>
						<button
							class="btn-secondary text-sm inline-flex items-center gap-2
								   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
							onclick={disconnectPrinter}
							disabled={disconnecting}
						>
							{#if disconnecting}
								<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-surface-400 border-t-white"></span>
							{/if}
							Disconnect
						</button>
					</div>
				{:else}
					<button
						class="btn-primary inline-flex items-center gap-2
							   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
						onclick={connectPrinter}
						disabled={connecting}
					>
						{#if connecting}
							<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white/30 border-t-white"></span>
						{/if}
						{connecting ? 'Connecting...' : 'Connect'}
					</button>
				{/if}
			</div>

			{#if connected && $printerState.firmware}
				<div class="card">
					<h2 class="text-lg font-semibold mb-2">Printer Info</h2>
					<div class="space-y-2 text-sm">
						<div class="flex justify-between">
							<span class="text-surface-500">Port</span>
							<span class="text-surface-300">{$printerState.port}</span>
						</div>
						<div class="flex justify-between">
							<span class="text-surface-500">Baud Rate</span>
							<span class="text-surface-300">{$printerState.baudrate.toLocaleString()}</span>
						</div>
						<div class="flex justify-between">
							<span class="text-surface-500">Firmware</span>
							<span class="text-surface-300 truncate max-w-[200px]">{$printerState.firmware}</span>
						</div>
					</div>
				</div>
			{/if}
		{/if}

		<!-- Notifications Tab -->
		{#if activeTab === 'notifications'}
			<div class="card">
				<h2 class="text-lg font-semibold mb-4">Browser Notifications</h2>
				<p class="text-sm text-surface-400 mb-4">Get notified when a print completes, even if the tab is in the background.</p>

				<div class="flex items-center justify-between">
					<div class="flex items-center gap-3">
						<button
							class="relative w-11 h-6 rounded-full transition-colors duration-200 {notificationsEnabled ? 'bg-accent' : 'bg-surface-700'}
								   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
							onclick={toggleNotifications}
						>
							<div class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 {notificationsEnabled ? 'translate-x-5' : ''}"></div>
						</button>
						<span class="text-sm text-surface-300">Print completion notifications</span>
					</div>
					{#if notificationsEnabled}
						<button class="btn-secondary text-xs px-3 py-1.5" onclick={testNotification}>
							Test
						</button>
					{/if}
				</div>
				{#if notificationPermission === 'denied'}
					<p class="text-xs text-amber-400 mt-2">Notifications are blocked by the browser. Check your browser settings.</p>
				{/if}
			</div>

			<div class="card">
				<h2 class="text-lg font-semibold mb-4">Completion Sound</h2>
				<p class="text-sm text-surface-400">A short beep plays when a print finishes. This is always on.</p>
			</div>
		{/if}

		<!-- Display Tab -->
		{#if activeTab === 'display'}
			<div class="card">
				<h2 class="text-lg font-semibold mb-4">Display Preferences</h2>

				<div class="space-y-6">
					<!-- Default jog distance -->
					<div>
						<label class="block text-sm text-surface-400 mb-2">Default Jog Distance</label>
						<div class="flex gap-1">
							{#each [0.1, 1, 10, 100] as dist}
								<button
									class="flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors
										   {defaultJogDistance === dist ? 'bg-accent text-white' : 'bg-surface-800 text-surface-400 hover:bg-surface-700'}
										   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
									onclick={() => { defaultJogDistance = dist; saveJogDistance(); }}
								>
									{dist}mm
								</button>
							{/each}
						</div>
					</div>

					<!-- Temperature unit -->
					<div>
						<label class="block text-sm text-surface-400 mb-2">Temperature Unit</label>
						<div class="flex gap-1">
							<button
								class="flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors
									   {tempUnit === 'C' ? 'bg-accent text-white' : 'bg-surface-800 text-surface-400 hover:bg-surface-700'}
									   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
								onclick={() => { tempUnit = 'C'; saveTempUnit(); }}
							>
								°C (Celsius)
							</button>
							<button
								class="flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors
									   {tempUnit === 'F' ? 'bg-accent text-white' : 'bg-surface-800 text-surface-400 hover:bg-surface-700'}
									   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
								onclick={() => { tempUnit = 'F'; saveTempUnit(); }}
							>
								°F (Fahrenheit)
							</button>
						</div>
					</div>
				</div>
			</div>

			<!-- Preheat Presets Management -->
			<div class="card">
				<h2 class="text-lg font-semibold mb-4">Custom Preheat Presets</h2>
				<p class="text-sm text-surface-400 mb-4">Add your own material presets for quick temperature setting.</p>

				{#if customPresets.length > 0}
					<div class="space-y-2 mb-4">
						{#each customPresets as preset, i}
							<div class="flex items-center justify-between bg-surface-800/50 rounded-lg px-3 py-2">
								<div>
									<span class="text-sm text-surface-200 font-medium">{preset.name}</span>
									<span class="text-xs text-surface-500 ml-2">{preset.hotend}/{preset.bed}°C</span>
								</div>
								<button
									class="btn-icon p-1 text-red-400/50 hover:text-red-400"
									onclick={() => removePreset(i)}
									title="Remove preset"
								>
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M6 18L18 6M6 6l12 12" />
									</svg>
								</button>
							</div>
						{/each}
					</div>
				{/if}

				<div class="flex gap-2">
					<input
						type="text"
						class="input flex-1"
						placeholder="Name (e.g. Silk PLA)"
						bind:value={newPresetName}
					/>
					<input
						type="number"
						class="input w-20"
						placeholder="Hotend"
						bind:value={newPresetHotend}
					/>
					<input
						type="number"
						class="input w-20"
						placeholder="Bed"
						bind:value={newPresetBed}
					/>
					<button
						class="btn-primary text-sm px-3
							   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
						onclick={addPreset}
						disabled={!newPresetName.trim()}
					>
						Add
					</button>
				</div>
			</div>
		{/if}

		<!-- System Tab -->
		{#if activeTab === 'system'}
			{#if health}
				<div class="card">
					<h2 class="text-lg font-semibold mb-4">System Health</h2>
					<div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
						<div>
							<span class="text-xs text-surface-500">CPU Temp</span>
							<p class="text-lg font-medium tabular-nums">{health.cpuTemp?.toFixed(1) || '0'}°C</p>
						</div>
						<div>
							<span class="text-xs text-surface-500">CPU Load</span>
							<p class="text-lg font-medium tabular-nums">{health.cpuUsage?.toFixed(1) || '0'}%</p>
						</div>
						<div>
							<span class="text-xs text-surface-500">Memory</span>
							<p class="text-lg font-medium tabular-nums">{health.memory?.percent || '0'}%</p>
						</div>
						<div>
							<span class="text-xs text-surface-500">Uptime</span>
							<p class="text-lg font-medium tabular-nums">
								{Math.floor((health.uptime || 0) / 3600)}h {Math.floor(((health.uptime || 0) % 3600) / 60)}m
							</p>
						</div>
					</div>
					<button
						class="btn-secondary text-xs mt-4
							   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
						onclick={loadHealth}
					>
						Refresh
					</button>
				</div>
			{:else}
				<div class="card">
					<h2 class="text-lg font-semibold mb-4">System Health</h2>
					<p class="text-sm text-surface-500">Loading system information...</p>
				</div>
			{/if}

			<div class="card">
				<h2 class="text-lg font-semibold mb-2">About PrintForge</h2>
				<div class="space-y-2 text-sm">
					<div class="flex justify-between">
						<span class="text-surface-500">Version</span>
						<span class="text-surface-300">0.1.0</span>
					</div>
					<div class="flex justify-between">
						<span class="text-surface-500">Platform</span>
						<span class="text-surface-300">Raspberry Pi 4</span>
					</div>
					<div class="flex justify-between">
						<span class="text-surface-500">Printer</span>
						<span class="text-surface-300">Ender 3 S1 Pro</span>
					</div>
				</div>
				<p class="text-xs text-surface-500 mt-4">
					Custom 3D printer control system. Built with SvelteKit + FastAPI.
				</p>
			</div>
		{/if}
	</div>
</div>
