<script lang="ts">
	import { fly, fade } from 'svelte/transition';
	import { onMount } from 'svelte';
	import { files, folders, currentPath, parentPath, filesLoading, refreshFiles, type GcodeFile, type Folder } from '$lib/stores/files';
	import { api } from '$lib/api';
	import { toast } from '$lib/stores/toast';
	import { confirmAction } from '$lib/stores/confirm';
	import { formatFileSize, formatDuration } from '$lib/utils';
	import PrintStartDialog from '$lib/components/PrintStartDialog.svelte';

	interface Props {
		open: boolean;
		onclose: () => void;
		disabled?: boolean;
	}

	let { open = $bindable(), onclose, disabled = false }: Props = $props();

	// Search + sort state
	let searchQuery = $state('');
	let debouncedQuery = $state('');
	let sortBy = $state<'name' | 'size' | 'time'>('name');
	let sortAsc = $state(true);

	// Per-row UI state
	let openMenu = $state<string | null>(null);
	let renamingFile = $state<string | null>(null);
	let renameValue = $state('');

	// Print dialog
	let printDialogOpen = $state(false);
	let printDialogFilename = $state('');

	// Debounce search
	let searchTimer: ReturnType<typeof setTimeout> | null = null;
	$effect(() => {
		const q = searchQuery;
		if (searchTimer) clearTimeout(searchTimer);
		searchTimer = setTimeout(() => { debouncedQuery = q; }, 150);
	});

	// Refresh when opened
	$effect(() => {
		if (open) {
			refreshFiles($currentPath);
		}
	});

	// Derived: breadcrumbs
	let breadcrumbs = $derived.by(() => {
		const path = $currentPath;
		if (!path) return [];
		const parts = path.split('/').filter(Boolean);
		return parts.map((part, i) => ({
			name: part,
			path: parts.slice(0, i + 1).join('/')
		}));
	});

	// Derived: filtered + sorted lists
	let filteredFolders = $derived.by(() => {
		const q = debouncedQuery.trim().toLowerCase();
		return q ? $folders.filter(f => f.name.toLowerCase().includes(q)) : $folders;
	});

	let filteredFiles = $derived.by(() => {
		let result = $files;
		const q = debouncedQuery.trim().toLowerCase();
		if (q) result = result.filter(f => f.filename.toLowerCase().includes(q));
		return [...result].sort((a, b) => {
			let cmp = 0;
			if (sortBy === 'name') cmp = a.filename.localeCompare(b.filename);
			else if (sortBy === 'size') cmp = a.fileSize - b.fileSize;
			else if (sortBy === 'time') cmp = (a.estimatedTime || 0) - (b.estimatedTime || 0);
			return sortAsc ? cmp : -cmp;
		});
	});

	function navigate(path: string) {
		openMenu = null;
		refreshFiles(path);
	}

	function goParent() {
		if ($parentPath !== null) navigate($parentPath);
	}

	function toggleSort(key: 'name' | 'size' | 'time') {
		if (sortBy === key) sortAsc = !sortAsc;
		else { sortBy = key; sortAsc = true; }
	}

	function startPrint(file: GcodeFile) {
		printDialogFilename = file.path || file.filename;
		printDialogOpen = true;
	}

	async function onPrintConfirm(spoolId: number | null) {
		const filename = printDialogFilename;
		printDialogOpen = false;
		printDialogFilename = '';
		try {
			await api.startPrint(filename, spoolId ?? undefined);
			toast.success('Print started: ' + filename);
			onclose(); // drawer closes on successful start
		} catch (e: any) {
			toast.error('Failed to start: ' + e.message);
		}
	}

	function onPrintCancel() {
		printDialogOpen = false;
		printDialogFilename = '';
	}

	async function deleteFile(file: GcodeFile) {
		openMenu = null;
		const ok = await confirmAction({
			title: 'Delete File',
			message: `Delete "${file.filename}"? This cannot be undone.`,
			confirmLabel: 'Delete',
			variant: 'danger'
		});
		if (!ok) return;
		try {
			await api.deleteFile(file.path || file.filename);
			toast.success('Deleted');
			await refreshFiles($currentPath);
		} catch (e: any) {
			toast.error('Delete failed: ' + e.message);
		}
	}

	function beginRename(file: GcodeFile) {
		openMenu = null;
		renamingFile = file.path || file.filename;
		renameValue = file.filename;
	}

	async function commitRename(file: GcodeFile) {
		const src = file.path || file.filename;
		const name = renameValue.trim();
		renamingFile = null;
		if (!name || name === file.filename) return;
		try {
			await api.renameFile(src, name);
			toast.success('Renamed');
			await refreshFiles($currentPath);
		} catch (e: any) {
			toast.error('Rename failed: ' + e.message);
		}
	}

	function cancelRename() {
		renamingFile = null;
		renameValue = '';
	}

	function onKeydown(e: KeyboardEvent) {
		if (!open) return;
		if (e.key === 'Escape') {
			// Don't steal Escape if a dialog is open
			if (printDialogOpen || renamingFile) return;
			onclose();
		}
	}

	function onBackdropClick() {
		if (!printDialogOpen) onclose();
	}
</script>

<svelte:window onkeydown={onKeydown} />

{#if open}
	<!-- Mobile/tablet backdrop — desktop (md+) keeps background interactive -->
	<button
		type="button"
		aria-label="Close files drawer"
		class="md:hidden fixed inset-0 bg-black/50 backdrop-blur-sm z-40"
		onclick={onBackdropClick}
		transition:fade={{ duration: 150 }}
	></button>

	<aside
		class="fixed right-0 top-14 bottom-0 md:bottom-0 w-full sm:w-[380px] bg-surface-900 border-l border-surface-700
		       shadow-2xl shadow-black/40 z-40 flex flex-col"
		transition:fly={{ x: 400, duration: 200 }}
		aria-label="Files"
	>
		<!-- Header -->
		<div class="flex items-center justify-between px-4 py-3 border-b border-surface-700 shrink-0">
			<div class="flex items-center gap-2">
				<svg class="w-4 h-4 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
				</svg>
				<h2 class="text-sm font-semibold text-surface-100">Files</h2>
				{#if disabled}
					<span class="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400">Printing</span>
				{/if}
			</div>
			<div class="flex items-center gap-1">
				<a
					href="/files"
					class="text-xs text-surface-500 hover:text-surface-300 px-2 py-1 rounded transition-colors"
					title="Open full Files page"
				>Full page</a>
				<button
					class="p-1.5 rounded hover:bg-surface-800 text-surface-400 hover:text-surface-200 transition-colors
					       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
					onclick={onclose}
					aria-label="Close files drawer"
					title="Close (Esc)"
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>
		</div>

		<!-- Search + sort -->
		<div class="px-4 py-3 border-b border-surface-700 space-y-2 shrink-0">
			<div class="relative">
				<svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
				</svg>
				<input
					type="text"
					placeholder="Search files..."
					bind:value={searchQuery}
					class="input w-full pl-8 pr-7 py-1.5 text-sm"
				/>
				{#if searchQuery}
					<button
						class="absolute right-1.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-surface-500 hover:text-surface-300 hover:bg-surface-800"
						onclick={() => { searchQuery = ''; }}
						aria-label="Clear search"
					>
						<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				{/if}
			</div>

			<!-- Sort pills -->
			<div class="flex items-center gap-1 text-xs">
				<span class="text-surface-500 mr-1">Sort:</span>
				{#each [['name','Name'],['time','Time'],['size','Size']] as [key, label]}
					{@const active = sortBy === key}
					<button
						class="px-2 py-0.5 rounded transition-colors flex items-center gap-0.5
						       {active ? 'bg-accent/15 text-accent' : 'text-surface-400 hover:bg-surface-800 hover:text-surface-200'}"
						onclick={() => toggleSort(key as 'name' | 'size' | 'time')}
					>
						{label}
						{#if active}
							<svg class="w-3 h-3 {sortAsc ? '' : 'rotate-180'}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
							</svg>
						{/if}
					</button>
				{/each}
			</div>
		</div>

		<!-- Breadcrumbs -->
		{#if breadcrumbs.length > 0 || $parentPath !== null}
			<div class="px-4 py-2 border-b border-surface-700 flex items-center gap-1 text-xs text-surface-400 overflow-x-auto shrink-0">
				<button
					class="hover:text-surface-200 transition-colors px-1 py-0.5 rounded"
					onclick={() => navigate('')}
				>Home</button>
				{#each breadcrumbs as crumb, i}
					<svg class="w-3 h-3 text-surface-600 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
					</svg>
					<button
						class="hover:text-surface-200 transition-colors px-1 py-0.5 rounded truncate max-w-[120px]
						       {i === breadcrumbs.length - 1 ? 'text-surface-200 font-medium' : ''}"
						onclick={() => navigate(crumb.path)}
					>{crumb.name}</button>
				{/each}
			</div>
		{/if}

		<!-- File list -->
		<div class="flex-1 overflow-y-auto">
			{#if $filesLoading && $files.length === 0 && $folders.length === 0}
				<div class="p-6 text-center text-xs text-surface-500">Loading...</div>
			{:else if filteredFolders.length === 0 && filteredFiles.length === 0}
				<div class="p-6 text-center text-sm text-surface-500">
					{debouncedQuery ? 'No matches.' : 'No files yet. Upload via the Files page.'}
				</div>
			{:else}
				<ul class="py-1">
					<!-- Folders -->
					{#each filteredFolders as folder (folder.path)}
						<li>
							<button
								class="w-full flex items-center gap-2 px-4 py-2 hover:bg-surface-800/70 text-left transition-colors
								       focus-visible:outline-none focus-visible:bg-surface-800"
								onclick={() => navigate(folder.path)}
							>
								<svg class="w-4 h-4 text-accent/80 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
								</svg>
								<span class="text-sm text-surface-200 truncate flex-1">{folder.name}</span>
								<span class="text-[10px] text-surface-500 tabular-nums">{folder.fileCount}</span>
							</button>
						</li>
					{/each}

					<!-- Files -->
					{#each filteredFiles as file (file.path || file.filename)}
						{@const isRenaming = renamingFile === (file.path || file.filename)}
						{@const menuId = file.path || file.filename}
						<li class="group relative">
							<div class="flex items-center gap-2 px-4 py-2 hover:bg-surface-800/70 transition-colors">
								<svg class="w-4 h-4 text-surface-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
								</svg>
								<div class="flex-1 min-w-0">
									{#if isRenaming}
										<!-- svelte-ignore a11y_autofocus -->
										<input
											class="input w-full py-0.5 text-sm"
											bind:value={renameValue}
											autofocus
											onkeydown={(e) => {
												if (e.key === 'Enter') commitRename(file);
												else if (e.key === 'Escape') cancelRename();
											}}
											onblur={() => commitRename(file)}
										/>
									{:else}
										<div class="text-sm text-surface-200 truncate" title={file.filename}>{file.filename}</div>
										<div class="flex items-center gap-2 text-[10px] text-surface-500 tabular-nums">
											<span>{formatFileSize(file.fileSize)}</span>
											{#if file.estimatedTime}
												<span>·</span>
												<span>{formatDuration(file.estimatedTime)}</span>
											{/if}
											{#if file.filamentUsedGrams}
												<span>·</span>
												<span>{file.filamentUsedGrams.toFixed(0)}g</span>
											{/if}
										</div>
									{/if}
								</div>

								{#if !isRenaming}
									<!-- Start print (primary) -->
									<button
										class="opacity-0 group-hover:opacity-100 focus-visible:opacity-100
										       btn-primary !py-1 !px-2 text-xs inline-flex items-center gap-1
										       disabled:opacity-50 disabled:cursor-not-allowed
										       transition-opacity"
										onclick={() => startPrint(file)}
										disabled={disabled}
										title={disabled ? 'Cannot start while printing' : 'Start print'}
									>
										<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
										</svg>
										Print
									</button>

									<!-- Overflow menu -->
									<button
										class="opacity-0 group-hover:opacity-100 focus-visible:opacity-100
										       p-1 rounded text-surface-500 hover:text-surface-200 hover:bg-surface-700
										       focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent/50
										       transition-opacity"
										onclick={(e) => { e.stopPropagation(); openMenu = openMenu === menuId ? null : menuId; }}
										aria-label="More actions"
									>
										<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
											<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
										</svg>
									</button>
								{/if}
							</div>

							{#if openMenu === menuId}
								<!-- eslint-disable-next-line -->
								<div
									class="absolute right-4 top-10 z-10 bg-surface-800 border border-surface-700 rounded-lg shadow-xl overflow-hidden min-w-[140px]"
									transition:fade={{ duration: 100 }}
								>
									<button
										class="w-full text-left text-xs px-3 py-2 hover:bg-surface-700 text-surface-200"
										onclick={() => beginRename(file)}
									>Rename</button>
									<button
										class="w-full text-left text-xs px-3 py-2 hover:bg-surface-700 text-red-400"
										onclick={() => deleteFile(file)}
									>Delete</button>
								</div>
							{/if}
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	</aside>
{/if}

<!-- Close any open overflow menu on outside click -->
{#if openMenu}
	<!-- svelte-ignore a11y_click_events_have_key_events -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-30"
		onclick={() => { openMenu = null; }}
	></div>
{/if}

<PrintStartDialog
	bind:open={printDialogOpen}
	filename={printDialogFilename}
	onconfirm={onPrintConfirm}
	oncancel={onPrintCancel}
/>
