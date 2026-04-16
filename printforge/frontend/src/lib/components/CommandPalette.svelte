<script lang="ts">
	import { fade, scale } from 'svelte/transition';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import { toast } from '$lib/stores/toast';
	import { confirmAction } from '$lib/stores/confirm';
	import { files, refreshFiles, type GcodeFile } from '$lib/stores/files';
	import { isPrinting, isPaused, isFinishing, isConnected } from '$lib/stores/printer';
	import PrintStartDialog from '$lib/components/PrintStartDialog.svelte';

	interface NavItem { path: string; label: string; icon: string; }

	interface Props {
		open: boolean;
		onclose: () => void;
		navItems: NavItem[];
	}

	let { open = $bindable(), onclose, navItems }: Props = $props();

	type Group = 'Actions' | 'Go to' | 'Files';
	interface Item {
		id: string;
		label: string;
		sublabel?: string;
		keywords?: string;
		group: Group;
		iconPath?: string;
		shortcut?: string;
		action: () => void | Promise<void>;
		disabled?: boolean;
		disabledReason?: string;
	}

	let query = $state('');
	let selectedIndex = $state(0);
	let inputEl = $state<HTMLInputElement | null>(null);
	let listEl = $state<HTMLElement | null>(null);

	// Print dialog (for starting prints from file results)
	let printDialogOpen = $state(false);
	let printDialogFilename = $state('');

	let printing = $derived($isPrinting);
	let paused = $derived($isPaused);
	let finishing = $derived($isFinishing);
	let connected = $derived($isConnected);
	let busy = $derived(printing || paused || finishing);

	// Build action items from current printer state
	let actions = $derived.by<Item[]>(() => {
		const items: Item[] = [];

		if (printing) {
			items.push({
				id: 'action:pause',
				label: 'Pause print',
				keywords: 'pause suspend halt',
				group: 'Actions',
				iconPath: 'M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z',
				action: async () => {
					try { await api.pausePrint(); toast.info('Print paused'); }
					catch (e: any) { toast.error('Pause failed: ' + e.message); }
				}
			});
		}
		if (paused) {
			items.push({
				id: 'action:resume',
				label: 'Resume print',
				keywords: 'resume continue play',
				group: 'Actions',
				iconPath: 'M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z',
				action: async () => {
					try { await api.resumePrint(); toast.success('Print resumed'); }
					catch (e: any) { toast.error('Resume failed: ' + e.message); }
				}
			});
		}
		if (printing || paused) {
			items.push({
				id: 'action:cancel',
				label: 'Cancel print',
				keywords: 'cancel stop abort',
				group: 'Actions',
				iconPath: 'M6 18L18 6M6 6l12 12',
				action: async () => {
					const ok = await confirmAction({
						title: 'Cancel Print',
						message: 'Cancel the current print? This cannot be undone.',
						confirmLabel: 'Cancel Print',
						variant: 'danger'
					});
					if (!ok) return;
					try { await api.cancelPrint(); toast.success('Print cancelled'); }
					catch (e: any) { toast.error('Cancel failed: ' + e.message); }
				}
			});
		}

		items.push({
			id: 'action:estop',
			label: 'Emergency stop',
			keywords: 'emergency stop halt panic estop m112',
			group: 'Actions',
			iconPath: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z',
			shortcut: 'Ctrl+E',
			action: async () => {
				try { await api.emergencyStop(); toast.warning('Emergency stop triggered'); }
				catch { toast.error('Emergency stop failed'); }
			}
		});

		items.push({
			id: 'action:home',
			label: 'Home all axes',
			keywords: 'home g28 xyz origin',
			group: 'Actions',
			iconPath: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6',
			disabled: busy,
			disabledReason: 'Disabled while printing',
			action: async () => {
				try { await api.home('XYZ'); toast.success('Homing all axes'); }
				catch (e: any) { toast.error('Home failed: ' + e.message); }
			}
		});

		items.push({
			id: 'action:motors-off',
			label: 'Disable motors',
			keywords: 'disable motors steppers m84 free',
			group: 'Actions',
			iconPath: 'M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636',
			disabled: busy,
			disabledReason: 'Disabled while printing',
			action: async () => {
				try { await api.motorsOff(); toast.info('Motors disabled'); }
				catch (e: any) { toast.error('Failed: ' + e.message); }
			}
		});

		items.push({
			id: 'action:disconnect',
			label: 'Disconnect printer',
			keywords: 'disconnect close serial',
			group: 'Actions',
			iconPath: 'M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1',
			disabled: busy || !connected,
			disabledReason: busy ? 'Disabled while printing' : 'Not connected',
			action: async () => {
				try { await api.disconnect(); toast.info('Disconnected'); }
				catch (e: any) { toast.error('Disconnect failed: ' + e.message); }
			}
		});

		return items;
	});

	// Route items
	let routes = $derived<Item[]>(
		navItems.map(n => ({
			id: 'route:' + n.path,
			label: 'Go to ' + n.label,
			keywords: n.label,
			group: 'Go to' as Group,
			iconPath: n.icon,
			action: () => goto(n.path)
		}))
	);

	// File items — only when we can actually print
	let fileItems = $derived<Item[]>(
		$files.map(f => ({
			id: 'file:' + (f.path || f.filename),
			label: f.filename,
			sublabel: f.estimatedTime ? formatDur(f.estimatedTime) : undefined,
			keywords: f.filename.replace(/[_\-.]/g, ' '),
			group: 'Files' as Group,
			iconPath: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
			disabled: busy,
			disabledReason: 'Cannot start while printing',
			action: () => startPrint(f)
		}))
	);

	let allItems = $derived([...actions, ...routes, ...fileItems]);

	// Fuzzy score — substring match on label + keywords, word-boundary boosted
	function score(item: Item, q: string): number {
		if (!q) return 1;
		const ql = q.toLowerCase();
		const label = item.label.toLowerCase();
		const kw = (item.keywords || '').toLowerCase();
		const combined = label + ' ' + kw;
		const labelIdx = label.indexOf(ql);
		if (labelIdx === 0) return 100;               // prefix match on label — top
		if (labelIdx > 0) return 80 - labelIdx;       // substring on label
		if (combined.includes(ql)) return 40;         // keyword / suffix match
		// Subsequence match (every char of q appears in order)
		let i = 0;
		for (const c of combined) {
			if (c === ql[i]) i++;
			if (i === ql.length) return 20;
		}
		return 0;
	}

	let filtered = $derived.by(() => {
		const q = query.trim();
		if (!q) {
			// No query: show actions + routes (hide files to reduce noise)
			return [...actions, ...routes];
		}
		return allItems
			.map(item => ({ item, s: score(item, q) }))
			.filter(({ s }) => s > 0)
			.sort((a, b) => b.s - a.s)
			.slice(0, 50)
			.map(({ item }) => item);
	});

	// Reset selection when filter changes
	$effect(() => {
		filtered;
		selectedIndex = 0;
	});

	// Refresh files when opened (so results are fresh)
	$effect(() => {
		if (open) {
			if (connected) refreshFiles('');
			// Focus the input after it renders
			queueMicrotask(() => inputEl?.focus());
			query = '';
			selectedIndex = 0;
		}
	});

	// Keep selected item visible
	$effect(() => {
		selectedIndex;
		if (!listEl) return;
		const el = listEl.querySelector<HTMLElement>(`[data-index="${selectedIndex}"]`);
		el?.scrollIntoView({ block: 'nearest' });
	});

	function formatDur(seconds: number): string {
		const h = Math.floor(seconds / 3600);
		const m = Math.floor((seconds % 3600) / 60);
		if (h > 0) return `${h}h ${m}m`;
		return `${m}m`;
	}

	function startPrint(file: GcodeFile) {
		printDialogFilename = file.path || file.filename;
		onclose(); // close palette so the dialog is cleanly in front
		printDialogOpen = true;
	}

	async function onPrintConfirm(spoolId: number | null) {
		const filename = printDialogFilename;
		printDialogOpen = false;
		printDialogFilename = '';
		try {
			await api.startPrint(filename, spoolId ?? undefined);
			toast.success('Print started: ' + filename);
		} catch (e: any) {
			toast.error('Failed to start: ' + e.message);
		}
	}
	function onPrintCancel() {
		printDialogOpen = false;
		printDialogFilename = '';
	}

	async function runItem(item: Item) {
		if (item.disabled) {
			if (item.disabledReason) toast.info(item.disabledReason);
			return;
		}
		const action = item.action;
		// Close palette before running unless it's startPrint which closes itself
		if (!item.id.startsWith('file:')) onclose();
		try {
			await action();
		} catch {
			/* action's own toast handles error */
		}
	}

	function onKeydown(e: KeyboardEvent) {
		if (!open) return;
		if (printDialogOpen) return; // let dialog own keys
		if (e.key === 'Escape') {
			e.preventDefault();
			onclose();
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			selectedIndex = Math.min(selectedIndex + 1, filtered.length - 1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			selectedIndex = Math.max(selectedIndex - 1, 0);
		} else if (e.key === 'Enter') {
			e.preventDefault();
			const item = filtered[selectedIndex];
			if (item) runItem(item);
		}
	}

	// Group visible items into sections for rendering
	let grouped = $derived.by(() => {
		const map = new Map<Group, Item[]>();
		for (const item of filtered) {
			if (!map.has(item.group)) map.set(item.group, []);
			map.get(item.group)!.push(item);
		}
		// Preserve a consistent section order
		const order: Group[] = ['Actions', 'Go to', 'Files'];
		return order
			.filter(g => map.has(g))
			.map(g => ({ group: g, items: map.get(g)! }));
	});

	// Compute flat index of each item (for arrow-key highlight)
	let flatIndexFor = $derived.by(() => {
		const m = new Map<string, number>();
		filtered.forEach((item, i) => m.set(item.id, i));
		return m;
	});
</script>

<svelte:window onkeydown={onKeydown} />

{#if open}
	<div
		class="fixed inset-0 z-[200] flex items-start justify-center p-4 pt-[10vh]"
		transition:fade={{ duration: 120 }}
	>
		<!-- eslint-disable-next-line -->
		<div class="absolute inset-0 bg-black/60 backdrop-blur-sm" onclick={onclose}></div>

		<div
			class="relative bg-surface-900 border border-surface-700 rounded-xl w-full max-w-xl shadow-2xl flex flex-col overflow-hidden"
			transition:scale={{ start: 0.96, duration: 120 }}
			role="dialog"
			aria-label="Command palette"
		>
			<!-- Search -->
			<div class="flex items-center gap-3 px-4 py-3 border-b border-surface-700">
				<svg class="w-4 h-4 text-surface-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
				</svg>
				<input
					bind:this={inputEl}
					bind:value={query}
					type="text"
					placeholder="Search files, actions, or pages..."
					class="flex-1 bg-transparent text-sm text-surface-100 placeholder-surface-500 focus:outline-none"
					autocomplete="off"
					spellcheck="false"
				/>
				<kbd class="text-[10px] text-surface-500 bg-surface-800 border border-surface-700 rounded px-1.5 py-0.5 shrink-0">Esc</kbd>
			</div>

			<!-- Results -->
			<div bind:this={listEl} class="max-h-[60vh] overflow-y-auto py-1">
				{#if filtered.length === 0}
					<div class="px-4 py-8 text-center text-sm text-surface-500">
						No matches for <span class="text-surface-300">"{query}"</span>
					</div>
				{:else}
					{#each grouped as section (section.group)}
						<div class="px-3 pt-2 pb-1 text-[10px] uppercase tracking-wider text-surface-500">
							{section.group}
						</div>
						{#each section.items as item (item.id)}
							{@const idx = flatIndexFor.get(item.id) ?? -1}
							{@const isSelected = idx === selectedIndex}
							<!-- svelte-ignore a11y_click_events_have_key_events -->
							<!-- svelte-ignore a11y_no_static_element_interactions -->
							<div
								data-index={idx}
								class="flex items-center gap-3 px-3 py-2 mx-1 rounded-lg cursor-pointer transition-colors
								       {isSelected ? 'bg-surface-800' : 'hover:bg-surface-800/60'}
								       {item.disabled ? 'opacity-50' : ''}"
								onclick={() => runItem(item)}
								onmouseenter={() => { selectedIndex = idx; }}
							>
								{#if item.iconPath}
									<svg class="w-4 h-4 text-surface-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d={item.iconPath} />
									</svg>
								{/if}
								<div class="flex-1 min-w-0 flex items-baseline gap-2">
									<span class="text-sm text-surface-200 truncate">{item.label}</span>
									{#if item.sublabel}
										<span class="text-[10px] text-surface-500 tabular-nums shrink-0">{item.sublabel}</span>
									{/if}
									{#if item.disabled && item.disabledReason}
										<span class="text-[10px] text-amber-500/70 shrink-0 ml-auto">{item.disabledReason}</span>
									{/if}
								</div>
								{#if item.shortcut && !item.disabled}
									<kbd class="text-[10px] text-surface-500 bg-surface-800 border border-surface-700 rounded px-1.5 py-0.5 shrink-0">{item.shortcut}</kbd>
								{/if}
							</div>
						{/each}
					{/each}
				{/if}
			</div>

			<!-- Footer hint -->
			<div class="flex items-center justify-between px-3 py-2 border-t border-surface-700 text-[10px] text-surface-500">
				<div class="flex items-center gap-2">
					<kbd class="bg-surface-800 border border-surface-700 rounded px-1 py-0.5">↑↓</kbd>
					<span>navigate</span>
					<kbd class="bg-surface-800 border border-surface-700 rounded px-1 py-0.5">↵</kbd>
					<span>run</span>
				</div>
				<div class="flex items-center gap-2">
					<kbd class="bg-surface-800 border border-surface-700 rounded px-1 py-0.5">Ctrl K</kbd>
					<span>toggle</span>
				</div>
			</div>
		</div>
	</div>
{/if}

<PrintStartDialog
	bind:open={printDialogOpen}
	filename={printDialogFilename}
	onconfirm={onPrintConfirm}
	oncancel={onPrintCancel}
/>
