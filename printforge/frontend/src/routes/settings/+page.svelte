<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { printerState, isConnected } from '$lib/stores/printer';
	import { toast } from '$lib/stores/toast';
	import { confirmAction } from '$lib/stores/confirm';

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
	let activeTab = $state<'connection' | 'printing' | 'filament' | 'notifications' | 'display' | 'system'>('connection');

	// Server-side settings (loaded from API)
	let serverSettings = $state<Record<string, string>>({});
	let settingsLoaded = $state(false);

	// Display settings
	let defaultJogDistance = $state(10);
	let tempUnit = $state<'C' | 'F'>('C');

	// Auto-connect settings
	let autoConnectEnabled = $state(false);
	let autoConnectPort = $state('auto');
	let autoConnectBaudrate = $state(115200);

	// Post-print settings
	let postPrintCooldown = $state(true);

	// Start/End G-code
	const DEFAULT_START_GCODE = `M140 S{bed_temp} ; Start heating bed (non-blocking)
M104 S{nozzle_temp} ; Start heating nozzle (non-blocking)
G28 ; Home all axes
G29 ; Auto bed leveling probe (remove if no ABL)
M190 S{bed_temp} ; Wait for bed to reach temperature
M109 S{nozzle_temp} ; Wait for nozzle to reach temperature
G92 E0 ; Reset extruder position
G1 Z2.0 F3000 ; Lift nozzle
G1 X0.1 Y20 Z0.3 F5000.0 ; Move to purge line start
G1 X0.1 Y200.0 Z0.3 F1500.0 E15 ; Draw first purge line
G1 X0.4 Y200.0 Z0.3 F5000.0 ; Shift over
G1 X0.4 Y20 Z0.3 F1500.0 E30 ; Draw second purge line
G92 E0 ; Reset extruder
G1 Z2.0 F3000 ; Lift nozzle
M117 Printing...`;

	const DEFAULT_END_GCODE = `G91 ; Relative positioning
G1 E-5 F1800 ; Retract filament
G1 Z10 F600 ; Lift Z 10mm
G90 ; Absolute positioning
G1 X0 Y220 F3000 ; Present print (move bed forward)
M104 S0 ; Turn off nozzle
M140 S0 ; Turn off bed
M106 S0 ; Turn off fan
M84 ; Disable steppers
M117 Print Complete`;

	let startGcode = $state(DEFAULT_START_GCODE);
	let endGcode = $state(DEFAULT_END_GCODE);

	// LCD progress settings
	let lcdProgressEnabled = $state(false);
	let lcdProgressInterval = $state(50);

	// Filament cost settings
	let filamentCostPerKg = $state(18);
	let filamentDensity = $state(1.24);

	// Printer profile
	let printerName = $state('Ender 3 S1 Pro');
	let buildVolumeX = $state(220);
	let buildVolumeY = $state(220);
	let buildVolumeZ = $state(270);
	let nozzleDiameter = $state(0.4);

	// Filament spool management
	interface Spool {
		id: number;
		name: string;
		material: string;
		color: string;
		total_weight_g: number;
		used_weight_g: number;
		cost_per_kg: number;
		active: number;
		notes: string;
	}
	let spools = $state<Spool[]>([]);
	let spoolsLoaded = $state(false);
	let showAddSpool = $state(false);
	let editingSpoolId = $state<number | null>(null);
	let newSpool = $state({ name: '', material: 'PLA', color: '#CCCCCC', total_weight_g: 1000, cost_per_kg: 18, notes: '' });
	const materials = ['PLA', 'PETG', 'ABS', 'TPU', 'ASA', 'Nylon', 'PVA', 'HIPS', 'PC', 'Other'];

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
		{ id: 'printing' as const, label: 'Printing', icon: 'M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z' },
		{ id: 'filament' as const, label: 'Filament', icon: 'M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z' },
		{ id: 'notifications' as const, label: 'Notifications', icon: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9' },
		{ id: 'display' as const, label: 'Display', icon: 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' },
		{ id: 'system' as const, label: 'System', icon: 'M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z' },
	];

	onMount(async () => {
		// Load from localStorage as fast cache
		notificationsEnabled = localStorage.getItem('printforge:notifications') === 'true';
		defaultJogDistance = parseInt(localStorage.getItem('printforge:jogDistance') || '10');
		tempUnit = (localStorage.getItem('printforge:tempUnit') as 'C' | 'F') || 'C';
		loadCustomPresetsFromLocal();

		// Load from server (authoritative)
		await Promise.all([loadSettings(), loadPorts(), loadHealth()]);
	});

	// Lazy-load spools when filament tab is first opened
	let apiKeyStatusLoaded = false;
	$effect(() => {
		if (activeTab === 'filament' && !spoolsLoaded) {
			loadSpools();
		}
		if (activeTab === 'system' && !apiKeyStatusLoaded) {
			apiKeyStatusLoaded = true;
			loadApiKeyStatus();
		}
	});

	async function loadSettings() {
		try {
			serverSettings = await api.getSettings();
			settingsLoaded = true;

			// Apply server values (override localStorage)
			if (serverSettings.jog_distance) {
				defaultJogDistance = parseInt(serverSettings.jog_distance);
			}
			if (serverSettings.temp_unit) {
				tempUnit = serverSettings.temp_unit as 'C' | 'F';
			}
			if (serverSettings.custom_presets) {
				try { customPresets = JSON.parse(serverSettings.custom_presets); } catch { /* keep local */ }
			}
			autoConnectEnabled = serverSettings.auto_connect_enabled === 'true';
			autoConnectPort = serverSettings.auto_connect_port || 'auto';
			autoConnectBaudrate = parseInt(serverSettings.auto_connect_baudrate || '115200');
			postPrintCooldown = serverSettings.post_print_cooldown !== 'false'; // default true
			if (serverSettings.start_gcode !== undefined) startGcode = serverSettings.start_gcode;
			if (serverSettings.end_gcode !== undefined) endGcode = serverSettings.end_gcode;
			lcdProgressEnabled = serverSettings.lcd_progress_enabled === 'true';
			lcdProgressInterval = parseInt(serverSettings.lcd_progress_interval || '50');
			filamentCostPerKg = parseFloat(serverSettings.filament_cost_per_kg || '18');
			filamentDensity = parseFloat(serverSettings.filament_density || '1.24');
			// Printer profile
			if (serverSettings.printer_profile) {
				try {
					const profile = JSON.parse(serverSettings.printer_profile);
					printerName = profile.name || 'Ender 3 S1 Pro';
					buildVolumeX = profile.buildVolume?.x || 220;
					buildVolumeY = profile.buildVolume?.y || 220;
					buildVolumeZ = profile.buildVolume?.z || 270;
					nozzleDiameter = profile.nozzleDiameter || 0.4;
				} catch { /* keep defaults */ }
			}
		} catch (e) {
			// Fall back to localStorage values
		}
	}

	async function saveSetting(key: string, value: string) {
		try {
			await api.updateSettings({ [key]: value });
			serverSettings[key] = value;
		} catch {
			toast.error('Failed to save setting');
		}
	}

	function loadCustomPresetsFromLocal() {
		try {
			const raw = localStorage.getItem('printforge:custom-presets');
			if (raw) customPresets = JSON.parse(raw);
		} catch { /* ignore */ }
	}

	function saveCustomPresets() {
		const json = JSON.stringify(customPresets);
		localStorage.setItem('printforge:custom-presets', json);
		saveSetting('custom_presets', json);
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

	async function toggleAutoConnect() {
		autoConnectEnabled = !autoConnectEnabled;
		await saveSetting('auto_connect_enabled', String(autoConnectEnabled));
		toast.info(autoConnectEnabled ? 'Auto-connect enabled' : 'Auto-connect disabled');
	}

	async function saveAutoConnectPort() {
		await saveSetting('auto_connect_port', autoConnectPort);
	}

	async function saveAutoConnectBaudrate() {
		await saveSetting('auto_connect_baudrate', String(autoConnectBaudrate));
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
		saveSetting('jog_distance', String(defaultJogDistance));
		toast.info(`Default jog distance: ${defaultJogDistance}mm`);
	}

	function saveTempUnit() {
		localStorage.setItem('printforge:tempUnit', tempUnit);
		saveSetting('temp_unit', tempUnit);
		toast.info(`Temperature unit: ${tempUnit}`);
	}

	// Filament spool functions
	async function loadSpools() {
		try {
			const data = await api.getSpools();
			spools = data.spools || [];
			spoolsLoaded = true;
		} catch {
			toast.error('Failed to load spools');
		}
	}

	async function addSpool() {
		if (!newSpool.name.trim()) return;
		try {
			await api.createSpool(newSpool);
			toast.success('Spool added');
			newSpool = { name: '', material: 'PLA', color: '#CCCCCC', total_weight_g: 1000, cost_per_kg: 18, notes: '' };
			showAddSpool = false;
			await loadSpools();
		} catch (e: any) {
			toast.error('Failed to add spool: ' + e.message);
		}
	}

	async function activateSpool(id: number) {
		try {
			await api.activateSpool(id);
			spools = spools.map(s => ({ ...s, active: s.id === id ? 1 : 0 }));
			toast.success('Spool activated');
		} catch (e: any) {
			toast.error('Failed to activate spool: ' + e.message);
		}
	}

	async function deleteSpool(id: number) {
		const ok = await confirmAction({
			title: 'Delete Spool',
			message: 'Are you sure you want to delete this spool? This cannot be undone.',
			confirmLabel: 'Delete',
			variant: 'danger'
		});
		if (!ok) return;
		try {
			await api.deleteSpool(id);
			spools = spools.filter(s => s.id !== id);
			toast.success('Spool deleted');
		} catch (e: any) {
			toast.error('Failed to delete spool: ' + e.message);
		}
	}

	async function saveSpoolEdit(spool: Spool) {
		try {
			await api.updateSpool(spool.id, {
				name: spool.name,
				material: spool.material,
				color: spool.color,
				total_weight_g: spool.total_weight_g,
				used_weight_g: spool.used_weight_g,
				cost_per_kg: spool.cost_per_kg,
				notes: spool.notes,
			});
			editingSpoolId = null;
			toast.success('Spool updated');
		} catch (e: any) {
			toast.error('Failed to update spool: ' + e.message);
		}
	}

	function spoolRemaining(spool: Spool): number {
		return Math.max(0, spool.total_weight_g - spool.used_weight_g);
	}

	function spoolPercent(spool: Spool): number {
		if (spool.total_weight_g <= 0) return 0;
		return Math.min(100, Math.max(0, (spoolRemaining(spool) / spool.total_weight_g) * 100));
	}

	// API Key management
	let apiKeyEnabled = $state(false);
	let apiKeyLoading = $state(false);
	let generatedKey = $state('');

	async function loadApiKeyStatus() {
		try {
			const data = await api.getApiKeyStatus();
			apiKeyEnabled = data.enabled;
		} catch { /* ignore */ }
	}

	async function generateApiKey() {
		apiKeyLoading = true;
		try {
			const data = await api.generateApiKey();
			generatedKey = data.api_key;
			apiKeyEnabled = true;
			// Auto-save to localStorage so current session keeps working
			const { setApiKey } = await import('$lib/api');
			setApiKey(data.api_key);
			toast.success('API key generated. Save it somewhere safe!');
		} catch (e: any) {
			toast.error('Failed to generate key: ' + e.message);
		} finally {
			apiKeyLoading = false;
		}
	}

	async function revokeApiKey() {
		const ok = await confirmAction({
			title: 'Revoke API Key',
			message: 'This will disable API key authentication. All requests will be allowed without a key.',
			confirmLabel: 'Revoke',
			variant: 'danger'
		});
		if (!ok) return;
		try {
			await api.revokeApiKey();
			apiKeyEnabled = false;
			generatedKey = '';
			const { setApiKey } = await import('$lib/api');
			setApiKey(null);
			toast.info('API key revoked');
		} catch (e: any) {
			toast.error('Failed to revoke key: ' + e.message);
		}
	}

	function copyApiKey() {
		navigator.clipboard.writeText(generatedKey);
		toast.success('API key copied to clipboard');
	}

	async function handleRestartService() {
		const ok = await confirmAction({
			title: 'Restart PrintForge',
			message: 'This will restart the PrintForge service. The page will reload when it comes back.',
			confirmLabel: 'Restart',
			variant: 'danger'
		});
		if (!ok) return;
		try {
			await api.restartService();
			toast.info('Restarting service...');
			// Wait and reload
			setTimeout(() => window.location.reload(), 5000);
		} catch (e: any) {
			toast.error('Failed: ' + e.message);
		}
	}

	async function handleRestartOS() {
		const ok = await confirmAction({
			title: 'Restart Raspberry Pi',
			message: 'This will reboot the entire system. PrintForge will be unavailable for about a minute.',
			confirmLabel: 'Restart Pi',
			variant: 'danger'
		});
		if (!ok) return;
		try {
			await api.restartOS();
			toast.warning('System rebooting...');
		} catch (e: any) {
			toast.error('Failed: ' + e.message);
		}
	}

	async function handleShutdownOS() {
		const ok = await confirmAction({
			title: 'Shut Down Raspberry Pi',
			message: 'This will power off the system. You will need physical access to turn it back on.',
			confirmLabel: 'Shut Down',
			variant: 'danger'
		});
		if (!ok) return;
		try {
			await api.shutdownOS();
			toast.warning('System shutting down...');
		} catch (e: any) {
			toast.error('Failed: ' + e.message);
		}
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

			<!-- Auto-Connect -->
			<div class="card">
				<h2 class="text-lg font-semibold mb-4">Auto-Connect</h2>
				<p class="text-sm text-surface-400 mb-4">Automatically connect to the printer when PrintForge starts.</p>

				<div class="space-y-4">
					<div class="flex items-center justify-between">
						<span class="text-sm text-surface-300">Enable auto-connect</span>
						<button
							class="relative w-11 h-6 rounded-full transition-colors duration-200 {autoConnectEnabled ? 'bg-accent' : 'bg-surface-700'}
								   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
							onclick={toggleAutoConnect}
						>
							<div class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 {autoConnectEnabled ? 'translate-x-5' : ''}"></div>
						</button>
					</div>

					{#if autoConnectEnabled}
						<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
							<div>
								<label class="block text-sm text-surface-400 mb-1">Preferred Port</label>
								<select class="input w-full" bind:value={autoConnectPort} onchange={saveAutoConnectPort}>
									<option value="auto">Auto-detect</option>
									{#each ports as port}
										<option value={port}>{port}</option>
									{/each}
								</select>
							</div>
							<div>
								<label class="block text-sm text-surface-400 mb-1">Baud Rate</label>
								<select class="input w-full" bind:value={autoConnectBaudrate} onchange={saveAutoConnectBaudrate}>
									{#each baudRates as rate}
										<option value={rate}>{rate.toLocaleString()}</option>
									{/each}
								</select>
							</div>
						</div>
					{/if}
				</div>
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

		<!-- Printing Tab -->
		{#if activeTab === 'printing'}
			<!-- Start G-code -->
			<div class="card">
				<h2 class="text-lg font-semibold mb-2">Start G-code</h2>
				<p class="text-sm text-surface-400 mb-3">
					Runs before every print. Homes the printer, levels the bed, heats up, and prints a purge line.
					Use <code class="text-accent text-xs">{'{nozzle_temp}'}</code> and <code class="text-accent text-xs">{'{bed_temp}'}</code> as placeholders — they are replaced with the temperatures from the G-code file.
				</p>
				<textarea
					class="input w-full font-mono text-xs leading-relaxed"
					rows="16"
					bind:value={startGcode}
					spellcheck="false"
				></textarea>
				<div class="flex items-center gap-2 mt-3">
					<button
						class="btn-primary text-sm"
						onclick={() => { saveSetting('start_gcode', startGcode); toast.success('Start G-code saved'); }}
					>
						Save
					</button>
					<button
						class="btn-secondary text-sm"
						onclick={() => { startGcode = DEFAULT_START_GCODE; saveSetting('start_gcode', DEFAULT_START_GCODE); toast.info('Reset to default'); }}
					>
						Reset to Default
					</button>
					<button
						class="btn-secondary text-sm"
						onclick={() => { startGcode = ''; saveSetting('start_gcode', ''); toast.info('Start G-code disabled'); }}
					>
						Disable
					</button>
				</div>
			</div>

			<!-- End G-code -->
			<div class="card">
				<h2 class="text-lg font-semibold mb-2">End G-code</h2>
				<p class="text-sm text-surface-400 mb-3">
					Runs after every completed print. Retracts filament, presents the print, and cools down.
				</p>
				<textarea
					class="input w-full font-mono text-xs leading-relaxed"
					rows="12"
					bind:value={endGcode}
					spellcheck="false"
				></textarea>
				<div class="flex items-center gap-2 mt-3">
					<button
						class="btn-primary text-sm"
						onclick={() => { saveSetting('end_gcode', endGcode); toast.success('End G-code saved'); }}
					>
						Save
					</button>
					<button
						class="btn-secondary text-sm"
						onclick={() => { endGcode = DEFAULT_END_GCODE; saveSetting('end_gcode', DEFAULT_END_GCODE); toast.info('Reset to default'); }}
					>
						Reset to Default
					</button>
					<button
						class="btn-secondary text-sm"
						onclick={() => { endGcode = ''; saveSetting('end_gcode', ''); toast.info('End G-code disabled'); }}
					>
						Disable
					</button>
				</div>
			</div>

			<!-- Post-Print Actions -->
			<div class="card">
				<h2 class="text-lg font-semibold mb-4">Post-Print Actions</h2>
				<p class="text-sm text-surface-400 mb-4">Actions to perform automatically when a print completes.</p>

				<div class="flex items-center justify-between">
					<div>
						<span class="text-sm text-surface-300">Auto cooldown</span>
						<p class="text-xs text-surface-500">Turn off hotend and bed heaters after print</p>
					</div>
					<button
						class="relative w-11 h-6 rounded-full transition-colors duration-200 {postPrintCooldown ? 'bg-accent' : 'bg-surface-700'}
							   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
						onclick={() => { postPrintCooldown = !postPrintCooldown; saveSetting('post_print_cooldown', String(postPrintCooldown)); }}
					>
						<div class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 {postPrintCooldown ? 'translate-x-5' : ''}"></div>
					</button>
				</div>
			</div>

			<!-- LCD Progress -->
			<div class="card">
				<h2 class="text-lg font-semibold mb-4">LCD Progress Display</h2>
				<p class="text-sm text-surface-400 mb-4">Show print progress on the printer's LCD screen via M117 commands.</p>

				<div class="space-y-4">
					<div class="flex items-center justify-between">
						<span class="text-sm text-surface-300">Show progress on LCD</span>
						<button
							class="relative w-11 h-6 rounded-full transition-colors duration-200 {lcdProgressEnabled ? 'bg-accent' : 'bg-surface-700'}
								   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
							onclick={() => { lcdProgressEnabled = !lcdProgressEnabled; saveSetting('lcd_progress_enabled', String(lcdProgressEnabled)); }}
						>
							<div class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200 {lcdProgressEnabled ? 'translate-x-5' : ''}"></div>
						</button>
					</div>

					{#if lcdProgressEnabled}
						<div>
							<label class="block text-sm text-surface-400 mb-1">Update every N lines</label>
							<input
								type="number"
								class="input w-32"
								min="10"
								max="500"
								bind:value={lcdProgressInterval}
								onchange={() => saveSetting('lcd_progress_interval', String(lcdProgressInterval))}
							/>
							<p class="text-xs text-surface-500 mt-1">Also updates on every layer change</p>
						</div>
					{/if}
				</div>
			</div>

			<!-- Filament Cost -->
			<div class="card">
				<h2 class="text-lg font-semibold mb-4">Filament Cost Estimation</h2>
				<p class="text-sm text-surface-400 mb-4">Configure filament costs to see price estimates on your files and print history.</p>

				<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
					<div>
						<label class="block text-sm text-surface-400 mb-1">Cost per kg ($)</label>
						<input
							type="number"
							class="input w-full"
							min="0"
							step="0.5"
							bind:value={filamentCostPerKg}
							onchange={() => saveSetting('filament_cost_per_kg', String(filamentCostPerKg))}
						/>
					</div>
					<div>
						<label class="block text-sm text-surface-400 mb-1">Density (g/cm³)</label>
						<input
							type="number"
							class="input w-full"
							min="0.5"
							max="3"
							step="0.01"
							bind:value={filamentDensity}
							onchange={() => saveSetting('filament_density', String(filamentDensity))}
						/>
						<p class="text-xs text-surface-500 mt-1">PLA: 1.24, PETG: 1.27, ABS: 1.04</p>
					</div>
				</div>
			</div>

			<!-- Printer Profile -->
			<div class="card">
				<h2 class="text-lg font-semibold mb-4">Printer Profile</h2>

				<div class="space-y-4">
					<div>
						<label class="block text-sm text-surface-400 mb-1">Printer Name</label>
						<input type="text" class="input w-full" bind:value={printerName} />
					</div>

					<div>
						<label class="block text-sm text-surface-400 mb-2">Build Volume (mm)</label>
						<div class="grid grid-cols-3 gap-3">
							<div>
								<label class="block text-xs text-surface-500 mb-1">X</label>
								<input type="number" class="input w-full" bind:value={buildVolumeX} />
							</div>
							<div>
								<label class="block text-xs text-surface-500 mb-1">Y</label>
								<input type="number" class="input w-full" bind:value={buildVolumeY} />
							</div>
							<div>
								<label class="block text-xs text-surface-500 mb-1">Z</label>
								<input type="number" class="input w-full" bind:value={buildVolumeZ} />
							</div>
						</div>
					</div>

					<div>
						<label class="block text-sm text-surface-400 mb-1">Nozzle Diameter (mm)</label>
						<input type="number" class="input w-32" step="0.1" min="0.1" max="1.5" bind:value={nozzleDiameter} />
					</div>

					<button
						class="btn-primary text-sm"
						onclick={() => {
							const profile = JSON.stringify({
								name: printerName,
								buildVolume: { x: buildVolumeX, y: buildVolumeY, z: buildVolumeZ },
								nozzleDiameter,
							});
							saveSetting('printer_profile', profile);
							toast.success('Printer profile saved');
						}}
					>
						Save Profile
					</button>
				</div>
			</div>
		{/if}

		<!-- Filament Tab -->
		{#if activeTab === 'filament'}
			<div class="card">
				<div class="flex items-center justify-between mb-4">
					<h2 class="text-lg font-semibold">Filament Spools</h2>
					<button
						class="btn-primary text-sm inline-flex items-center gap-1.5"
						onclick={() => showAddSpool = !showAddSpool}
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
						</svg>
						Add Spool
					</button>
				</div>
				<p class="text-sm text-surface-400 mb-4">
					Track your filament spools. The active spool is used for automatic filament deduction after prints.
				</p>

				<!-- Add Spool Form -->
				{#if showAddSpool}
					<div class="bg-surface-800/50 rounded-lg p-4 mb-4 space-y-3">
						<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
							<div>
								<label class="block text-xs text-surface-400 mb-1">Name</label>
								<input type="text" class="input w-full" placeholder="e.g. White PLA" bind:value={newSpool.name} />
							</div>
							<div>
								<label class="block text-xs text-surface-400 mb-1">Material</label>
								<select class="input w-full" bind:value={newSpool.material}>
									{#each materials as mat}
										<option value={mat}>{mat}</option>
									{/each}
								</select>
							</div>
							<div>
								<label class="block text-xs text-surface-400 mb-1">Color</label>
								<div class="flex items-center gap-2">
									<input type="color" class="w-8 h-8 rounded border-0 cursor-pointer" bind:value={newSpool.color} />
									<input type="text" class="input flex-1" bind:value={newSpool.color} />
								</div>
							</div>
							<div>
								<label class="block text-xs text-surface-400 mb-1">Total Weight (g)</label>
								<input type="number" class="input w-full" min="1" bind:value={newSpool.total_weight_g} />
							</div>
							<div>
								<label class="block text-xs text-surface-400 mb-1">Cost per kg ($)</label>
								<input type="number" class="input w-full" min="0" step="0.5" bind:value={newSpool.cost_per_kg} />
							</div>
							<div>
								<label class="block text-xs text-surface-400 mb-1">Notes</label>
								<input type="text" class="input w-full" placeholder="Optional notes" bind:value={newSpool.notes} />
							</div>
						</div>
						<div class="flex gap-2 justify-end">
							<button class="btn-secondary text-sm" onclick={() => showAddSpool = false}>Cancel</button>
							<button class="btn-primary text-sm" onclick={addSpool} disabled={!newSpool.name.trim()}>Create Spool</button>
						</div>
					</div>
				{/if}

				<!-- Spool List -->
				{#if !spoolsLoaded}
					<p class="text-sm text-surface-500">Loading spools...</p>
				{:else if spools.length === 0}
					<div class="text-center py-8">
						<svg class="w-12 h-12 text-surface-700 mx-auto mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
						</svg>
						<p class="text-sm text-surface-500">No spools added yet</p>
						<p class="text-xs text-surface-600 mt-1">Add a spool to start tracking filament usage</p>
					</div>
				{:else}
					<div class="space-y-3">
						{#each spools as spool (spool.id)}
							<div class="bg-surface-800/50 rounded-lg p-3 {spool.active ? 'ring-1 ring-accent/40' : ''}">
								{#if editingSpoolId === spool.id}
									<!-- Edit mode -->
									<div class="space-y-3">
										<div class="grid grid-cols-2 gap-3">
											<div>
												<label class="block text-xs text-surface-400 mb-1">Name</label>
												<input type="text" class="input w-full text-sm" bind:value={spool.name} />
											</div>
											<div>
												<label class="block text-xs text-surface-400 mb-1">Material</label>
												<select class="input w-full text-sm" bind:value={spool.material}>
													{#each materials as mat}
														<option value={mat}>{mat}</option>
													{/each}
												</select>
											</div>
											<div>
												<label class="block text-xs text-surface-400 mb-1">Color</label>
												<div class="flex items-center gap-2">
													<input type="color" class="w-6 h-6 rounded border-0 cursor-pointer" bind:value={spool.color} />
													<input type="text" class="input flex-1 text-sm" bind:value={spool.color} />
												</div>
											</div>
											<div>
												<label class="block text-xs text-surface-400 mb-1">Total (g)</label>
												<input type="number" class="input w-full text-sm" min="1" bind:value={spool.total_weight_g} />
											</div>
											<div>
												<label class="block text-xs text-surface-400 mb-1">Used (g)</label>
												<input type="number" class="input w-full text-sm" min="0" bind:value={spool.used_weight_g} />
											</div>
											<div>
												<label class="block text-xs text-surface-400 mb-1">Cost/kg ($)</label>
												<input type="number" class="input w-full text-sm" min="0" step="0.5" bind:value={spool.cost_per_kg} />
											</div>
										</div>
										<div>
											<label class="block text-xs text-surface-400 mb-1">Notes</label>
											<input type="text" class="input w-full text-sm" bind:value={spool.notes} />
										</div>
										<div class="flex gap-2 justify-end">
											<button class="btn-secondary text-xs px-3 py-1.5" onclick={() => { editingSpoolId = null; loadSpools(); }}>Cancel</button>
											<button class="btn-primary text-xs px-3 py-1.5" onclick={() => saveSpoolEdit(spool)}>Save</button>
										</div>
									</div>
								{:else}
									<!-- Display mode -->
									<div class="flex items-start gap-3">
										<!-- Color dot -->
										<div class="w-8 h-8 rounded-full shrink-0 mt-0.5 border border-surface-600" style="background-color: {spool.color}"></div>
										<div class="flex-1 min-w-0">
											<div class="flex items-center gap-2 mb-1">
												<span class="text-sm font-medium text-surface-200 truncate">{spool.name}</span>
												<span class="text-xs px-1.5 py-0.5 rounded bg-surface-700 text-surface-400">{spool.material}</span>
												{#if spool.active}
													<span class="text-xs px-1.5 py-0.5 rounded bg-accent/20 text-accent font-medium">Active</span>
												{/if}
											</div>
											<!-- Progress bar -->
											<div class="flex items-center gap-2 mb-1">
												<div class="flex-1 h-2 bg-surface-700 rounded-full overflow-hidden">
													<div
														class="h-full rounded-full transition-all duration-300 {spoolPercent(spool) > 20 ? 'bg-accent' : spoolPercent(spool) > 5 ? 'bg-amber-500' : 'bg-red-500'}"
														style="width: {spoolPercent(spool)}%"
													></div>
												</div>
												<span class="text-xs text-surface-400 tabular-nums shrink-0">
													{spoolRemaining(spool).toFixed(0)}g / {spool.total_weight_g}g
												</span>
											</div>
											<div class="flex items-center gap-3 text-xs text-surface-500">
												<span>${spool.cost_per_kg}/kg</span>
												<span>{spoolPercent(spool).toFixed(0)}% remaining</span>
												{#if spool.notes}
													<span class="truncate">{spool.notes}</span>
												{/if}
											</div>
										</div>
										<!-- Actions -->
										<div class="flex items-center gap-1 shrink-0">
											{#if !spool.active}
												<button
													class="p-1.5 rounded-lg text-surface-500 hover:text-accent hover:bg-surface-700 transition-colors"
													onclick={() => activateSpool(spool.id)}
													title="Set as active spool"
												>
													<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
														<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
													</svg>
												</button>
											{/if}
											<button
												class="p-1.5 rounded-lg text-surface-500 hover:text-surface-200 hover:bg-surface-700 transition-colors"
												onclick={() => editingSpoolId = spool.id}
												title="Edit spool"
											>
												<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
												</svg>
											</button>
											<button
												class="p-1.5 rounded-lg text-surface-500 hover:text-red-400 hover:bg-surface-700 transition-colors"
												onclick={() => deleteSpool(spool.id)}
												title="Delete spool"
											>
												<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
													<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
												</svg>
											</button>
										</div>
									</div>
								{/if}
							</div>
						{/each}
					</div>
				{/if}
			</div>
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
								Celsius
							</button>
							<button
								class="flex-1 py-2.5 rounded-lg text-sm font-medium transition-colors
									   {tempUnit === 'F' ? 'bg-accent text-white' : 'bg-surface-800 text-surface-400 hover:bg-surface-700'}
									   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
								onclick={() => { tempUnit = 'F'; saveTempUnit(); }}
							>
								Fahrenheit
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

			<!-- API Key Authentication -->
			<div class="card">
				<h2 class="text-lg font-semibold mb-4">Access Control</h2>
				<p class="text-sm text-surface-400 mb-4">
					Protect your PrintForge instance with an API key. When enabled, all API requests must include the key.
				</p>

				{#if apiKeyEnabled}
					<div class="flex items-center gap-3 mb-4">
						<div class="w-2 h-2 rounded-full bg-emerald-400"></div>
						<span class="text-sm text-surface-300">API key authentication is active</span>
					</div>

					{#if generatedKey}
						<div class="bg-surface-800/50 rounded-lg p-3 mb-4">
							<p class="text-xs text-amber-400 mb-2">Save this key now — it cannot be shown again:</p>
							<div class="flex items-center gap-2">
								<code class="flex-1 text-xs text-surface-200 bg-surface-900 rounded px-2 py-1.5 font-mono break-all select-all">
									{generatedKey}
								</code>
								<button class="btn-secondary text-xs px-2 py-1.5 shrink-0" onclick={copyApiKey}>
									Copy
								</button>
							</div>
						</div>
					{/if}

					<div class="flex gap-2">
						<button
							class="btn-secondary text-sm"
							onclick={generateApiKey}
							disabled={apiKeyLoading}
						>
							Regenerate Key
						</button>
						<button
							class="text-sm px-3 py-1.5 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
							onclick={revokeApiKey}
						>
							Revoke Key
						</button>
					</div>
				{:else}
					<div class="flex items-center gap-3 mb-4">
						<div class="w-2 h-2 rounded-full bg-surface-600"></div>
						<span class="text-sm text-surface-400">No API key configured — open access</span>
					</div>
					<button
						class="btn-primary text-sm"
						onclick={generateApiKey}
						disabled={apiKeyLoading}
					>
						{apiKeyLoading ? 'Generating...' : 'Generate API Key'}
					</button>
				{/if}
			</div>

			<!-- Power & Service Controls -->
			<div class="card">
				<h2 class="text-lg font-semibold mb-4">Power & Service</h2>
				<p class="text-sm text-surface-400 mb-4">Control the PrintForge service and Raspberry Pi power.</p>

				<div class="space-y-3">
					<button
						class="w-full flex items-center justify-between bg-surface-800 hover:bg-surface-700 rounded-lg px-4 py-3 transition-colors
							   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
						onclick={handleRestartService}
					>
						<div class="flex items-center gap-3">
							<svg class="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
							</svg>
							<div class="text-left">
								<p class="text-sm font-medium text-surface-200">Restart PrintForge</p>
								<p class="text-xs text-surface-500">Restart the application service</p>
							</div>
						</div>
						<svg class="w-4 h-4 text-surface-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5l7 7-7 7" />
						</svg>
					</button>

					<button
						class="w-full flex items-center justify-between bg-surface-800 hover:bg-surface-700 rounded-lg px-4 py-3 transition-colors
							   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
						onclick={handleRestartOS}
					>
						<div class="flex items-center gap-3">
							<svg class="w-5 h-5 text-orange-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
							</svg>
							<div class="text-left">
								<p class="text-sm font-medium text-surface-200">Restart Raspberry Pi</p>
								<p class="text-xs text-surface-500">Reboot the entire system</p>
							</div>
						</div>
						<svg class="w-4 h-4 text-surface-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5l7 7-7 7" />
						</svg>
					</button>

					<button
						class="w-full flex items-center justify-between bg-surface-800 hover:bg-surface-700 rounded-lg px-4 py-3 transition-colors
							   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
						onclick={handleShutdownOS}
					>
						<div class="flex items-center gap-3">
							<svg class="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M18.364 5.636a9 9 0 11-12.728 0M12 3v9" />
							</svg>
							<div class="text-left">
								<p class="text-sm font-medium text-surface-200">Shut Down</p>
								<p class="text-xs text-surface-500">Power off the Raspberry Pi</p>
							</div>
						</div>
						<svg class="w-4 h-4 text-surface-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 5l7 7-7 7" />
						</svg>
					</button>
				</div>
			</div>

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
						<span class="text-surface-300">{printerName}</span>
					</div>
				</div>
				<p class="text-xs text-surface-500 mt-4">
					Custom 3D printer control system. Built with SvelteKit + FastAPI.
				</p>
			</div>
		{/if}
	</div>
</div>
