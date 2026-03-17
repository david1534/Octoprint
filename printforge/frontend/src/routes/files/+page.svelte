<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import FileUpload from '$lib/components/FileUpload.svelte';
	import { files, folders, currentPath, parentPath, refreshFiles, type GcodeFile, type Folder } from '$lib/stores/files';
	import { api } from '$lib/api';
	import { printerState } from '$lib/stores/printer';
	import { toast } from '$lib/stores/toast';
	import { confirmAction } from '$lib/stores/confirm';
	import { formatFileSize, formatDuration } from '$lib/utils';
	import EmptyState from '$lib/components/EmptyState.svelte';

	let isConnected = $derived($printerState.status !== 'disconnected');
	let isPrinting = $derived($printerState.status === 'printing' || $printerState.status === 'paused');
	let loading = $state('');
	let diskUsage = $state<{ free: number; total: number } | null>(null);
	let diskPct = $derived(diskUsage ? ((diskUsage.total - diskUsage.free) / diskUsage.total) * 100 : 0);

	// Search & sort
	let searchQuery = $state('');
	let sortBy = $state<'name' | 'size' | 'time'>('name');
	let sortAsc = $state(true);
	let viewMode = $state<'list' | 'grid'>('list');
	let expandedFile = $state<string | null>(null);

	// Batch selection
	let selectedFiles = $state<Set<string>>(new Set());
	let selectMode = $state(false);

	// New folder dialog
	let showNewFolder = $state(false);
	let newFolderName = $state('');

	// Breadcrumbs
	let breadcrumbs = $derived(() => {
		const path = $currentPath;
		if (!path) return [];
		const parts = path.split('/').filter(Boolean);
		return parts.map((part, i) => ({
			name: part,
			path: parts.slice(0, i + 1).join('/')
		}));
	});

	// Filtered and sorted files
	let filteredFiles = $derived(() => {
		let result = $files;
		if (searchQuery.trim()) {
			const q = searchQuery.toLowerCase();
			result = result.filter(f => f.filename.toLowerCase().includes(q));
		}
		result = [...result].sort((a, b) => {
			let cmp = 0;
			if (sortBy === 'name') cmp = a.filename.localeCompare(b.filename);
			else if (sortBy === 'size') cmp = a.fileSize - b.fileSize;
			else if (sortBy === 'time') cmp = (a.estimatedTime || 0) - (b.estimatedTime || 0);
			return sortAsc ? cmp : -cmp;
		});
		return result;
	});

	let filteredFolders = $derived(() => {
		if (!searchQuery.trim()) return $folders;
		const q = searchQuery.toLowerCase();
		return $folders.filter(f => f.name.toLowerCase().includes(q));
	});

	let allSelected = $derived(
		$files.length > 0 && selectedFiles.size === $files.length
	);

	onMount(() => {
		refreshFiles('');
		loadDiskUsage();
	});

	async function loadDiskUsage() {
		try {
			diskUsage = await api.getDiskUsage();
		} catch { /* Not critical */ }
	}

	function navigateToFolder(path: string) {
		searchQuery = '';
		expandedFile = null;
		selectedFiles = new Set();
		selectMode = false;
		refreshFiles(path);
	}

	function goUp() {
		if ($parentPath !== null && $parentPath !== '.') {
			navigateToFolder($parentPath);
		} else {
			navigateToFolder('');
		}
	}

	function toggleSort(field: typeof sortBy) {
		if (sortBy === field) {
			sortAsc = !sortAsc;
		} else {
			sortBy = field;
			sortAsc = true;
		}
	}

	function toggleSelectAll() {
		if (allSelected) {
			selectedFiles = new Set();
		} else {
			selectedFiles = new Set($files.map(f => f.path || f.filename));
		}
	}

	function toggleSelect(filePath: string) {
		const next = new Set(selectedFiles);
		if (next.has(filePath)) {
			next.delete(filePath);
		} else {
			next.add(filePath);
		}
		selectedFiles = next;
	}

	async function createFolder() {
		if (!newFolderName.trim()) return;
		const folderPath = $currentPath ? `${$currentPath}/${newFolderName.trim()}` : newFolderName.trim();
		try {
			await api.createFolder(folderPath);
			toast.success(`Folder "${newFolderName.trim()}" created`);
			newFolderName = '';
			showNewFolder = false;
			refreshFiles($currentPath);
		} catch (e: any) {
			toast.error('Failed to create folder: ' + e.message);
		}
	}

	async function startPrint(file: GcodeFile) {
		const ok = await confirmAction({
			title: 'Start Print',
			message: `Start printing "${file.filename}"?`,
			confirmLabel: 'Start Print',
			variant: 'primary'
		});
		if (!ok) return;
		loading = 'print:' + file.path;
		try {
			await api.startPrint(file.path || file.filename);
			toast.success('Print started: ' + file.filename);
			goto('/');
		} catch (e: any) {
			toast.error('Failed to start print: ' + e.message);
		} finally {
			loading = '';
		}
	}

	async function deleteFile(file: GcodeFile) {
		const ok = await confirmAction({
			title: 'Delete File',
			message: `Delete "${file.filename}"? This cannot be undone.`,
			confirmLabel: 'Delete',
			variant: 'danger'
		});
		if (!ok) return;
		loading = 'delete:' + file.path;
		try {
			await api.deleteFile(file.path || file.filename);
			await refreshFiles($currentPath);
			await loadDiskUsage();
			selectedFiles.delete(file.path);
			selectedFiles = new Set(selectedFiles);
			toast.success('Deleted: ' + file.filename);
		} catch (e: any) {
			toast.error('Failed to delete: ' + e.message);
		} finally {
			loading = '';
		}
	}

	async function deleteFolder(folder: Folder) {
		const ok = await confirmAction({
			title: 'Delete Folder',
			message: `Delete folder "${folder.name}"? It must be empty.`,
			confirmLabel: 'Delete',
			variant: 'danger'
		});
		if (!ok) return;
		try {
			await api.deleteFolder(folder.path);
			toast.success('Deleted folder: ' + folder.name);
			refreshFiles($currentPath);
		} catch (e: any) {
			toast.error(e.message);
		}
	}

	async function batchDelete() {
		if (selectedFiles.size === 0) return;
		const paths = Array.from(selectedFiles);
		const ok = await confirmAction({
			title: 'Delete Files',
			message: `Delete ${paths.length} file${paths.length > 1 ? 's' : ''}? This cannot be undone.`,
			confirmLabel: 'Delete All',
			variant: 'danger'
		});
		if (!ok) return;
		loading = 'batch-delete';
		try {
			for (const path of paths) {
				await api.deleteFile(path);
			}
			selectedFiles = new Set();
			selectMode = false;
			await refreshFiles($currentPath);
			await loadDiskUsage();
			toast.success(`Deleted ${paths.length} file${paths.length > 1 ? 's' : ''}`);
		} catch (e: any) {
			toast.error('Batch delete failed: ' + e.message);
		} finally {
			loading = '';
		}
	}

	function toggleExpand(filePath: string) {
		expandedFile = expandedFile === filePath ? null : filePath;
	}
</script>

<svelte:head>
	<title>PrintForge - Files</title>
</svelte:head>

<div class="flex items-center justify-between mb-4">
	<h1 class="text-xl font-bold">G-code Files</h1>
	<span class="text-sm text-surface-500">
		{$folders.length > 0 ? `${$folders.length} folder${$folders.length !== 1 ? 's' : ''}, ` : ''}
		{$files.length} file{$files.length !== 1 ? 's' : ''}
	</span>
</div>

<!-- Breadcrumb navigation -->
{#if $currentPath}
	<div class="flex items-center gap-1 mb-4 text-sm overflow-x-auto">
		<button
			class="text-accent hover:text-accent-hover transition-colors shrink-0"
			onclick={() => navigateToFolder('')}
		>
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
			</svg>
		</button>
		{#each breadcrumbs() as crumb, i}
			<span class="text-surface-600 shrink-0">/</span>
			{#if i === breadcrumbs().length - 1}
				<span class="text-surface-200 font-medium truncate">{crumb.name}</span>
			{:else}
				<button
					class="text-accent hover:text-accent-hover transition-colors truncate"
					onclick={() => navigateToFolder(crumb.path)}
				>
					{crumb.name}
				</button>
			{/if}
		{/each}
	</div>
{/if}

<!-- Upload area -->
<div class="mb-4">
	<FileUpload />
</div>

<!-- Disk usage -->
{#if diskUsage}
	<div class="mb-4">
		<div class="flex justify-between text-xs text-surface-400 mb-1">
			<span>Disk Usage</span>
			<span>{formatFileSize(diskUsage.total - diskUsage.free)} / {formatFileSize(diskUsage.total)}</span>
		</div>
		<div class="w-full h-2 bg-surface-800 rounded-full overflow-hidden">
			<div
				class="h-full rounded-full transition-all duration-500 {diskPct > 90 ? 'bg-red-500' : diskPct > 75 ? 'bg-amber-500' : 'bg-accent'}"
				style="width: {diskPct.toFixed(1)}%"
			></div>
		</div>
		<p class="text-xs text-surface-500 mt-1">{formatFileSize(diskUsage.free)} free</p>
	</div>
{/if}

<!-- Toolbar -->
{#if $files.length > 0 || $folders.length > 0}
	<div class="flex flex-wrap items-center gap-2 mb-4">
		<!-- Search -->
		<div class="relative flex-1 min-w-[200px]">
			<svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
			</svg>
			<input
				type="text"
				placeholder="Search files..."
				class="input w-full pl-9 py-1.5 text-sm"
				bind:value={searchQuery}
			/>
		</div>

		<!-- Sort buttons -->
		<div class="flex items-center gap-1">
			{#each [['name', 'Name'], ['size', 'Size'], ['time', 'Time']] as [field, label]}
				<button
					class="px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors
						   {sortBy === field ? 'bg-accent/10 text-accent' : 'text-surface-400 hover:bg-surface-800 hover:text-surface-200'}"
					onclick={() => toggleSort(field as typeof sortBy)}
				>
					{label} {sortBy === field ? (sortAsc ? '↑' : '↓') : ''}
				</button>
			{/each}
		</div>

		<!-- View mode toggle -->
		<div class="flex items-center border border-surface-700 rounded-lg overflow-hidden">
			<button
				class="p-1.5 transition-colors {viewMode === 'list' ? 'bg-surface-700 text-surface-100' : 'text-surface-500 hover:text-surface-300'}"
				onclick={() => viewMode = 'list'}
				title="List view"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 6h16M4 12h16M4 18h16" />
				</svg>
			</button>
			<button
				class="p-1.5 transition-colors {viewMode === 'grid' ? 'bg-surface-700 text-surface-100' : 'text-surface-500 hover:text-surface-300'}"
				onclick={() => viewMode = 'grid'}
				title="Grid view"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
				</svg>
			</button>
		</div>

		<!-- New folder button -->
		<button
			class="px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors text-surface-400 hover:bg-surface-800 hover:text-surface-200"
			onclick={() => showNewFolder = !showNewFolder}
			title="New folder"
		>
			<svg class="w-4 h-4 inline-block mr-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
			</svg>
			New Folder
		</button>

		<!-- Batch select -->
		<button
			class="px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors
				   {selectMode ? 'bg-accent/10 text-accent' : 'text-surface-400 hover:bg-surface-800 hover:text-surface-200'}"
			onclick={() => { selectMode = !selectMode; if (!selectMode) selectedFiles = new Set(); }}
		>
			{selectMode ? 'Cancel' : 'Select'}
		</button>
	</div>
{/if}

<!-- New folder input -->
{#if showNewFolder}
	<div class="flex gap-2 mb-4">
		<input
			type="text"
			class="input flex-1 text-sm"
			placeholder="Folder name..."
			bind:value={newFolderName}
			onkeydown={(e) => { if (e.key === 'Enter') createFolder(); }}
		/>
		<button class="btn-primary text-sm px-3" onclick={createFolder} disabled={!newFolderName.trim()}>
			Create
		</button>
		<button class="btn-secondary text-sm px-3" onclick={() => { showNewFolder = false; newFolderName = ''; }}>
			Cancel
		</button>
	</div>
{/if}

<!-- Batch actions bar -->
{#if selectMode && selectedFiles.size > 0}
	<div class="flex items-center gap-3 mb-4 px-3 py-2 bg-surface-800 rounded-lg">
		<button
			class="text-xs text-surface-400 hover:text-surface-200 transition-colors"
			onclick={toggleSelectAll}
		>
			{allSelected ? 'Deselect all' : 'Select all'}
		</button>
		<span class="text-xs text-surface-500">{selectedFiles.size} selected</span>
		<button
			class="ml-auto btn-danger text-xs px-3 py-1.5 inline-flex items-center gap-1.5"
			onclick={batchDelete}
			disabled={loading === 'batch-delete'}
		>
			{#if loading === 'batch-delete'}
				<span class="animate-spin rounded-full h-3 w-3 border-2 border-red-300/30 border-t-white"></span>
			{:else}
				<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
				</svg>
			{/if}
			Delete selected
		</button>
	</div>
{/if}

<!-- Content listing -->
{#if $files.length === 0 && $folders.length === 0 && !$currentPath}
	<EmptyState
		title="No Files Uploaded"
		description="Drop a .gcode file above or click browse to get started"
	>
		{#snippet icon()}
			<svg class="w-8 h-8 text-surface-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
			</svg>
		{/snippet}
	</EmptyState>
{:else if $files.length === 0 && $folders.length === 0 && $currentPath}
	<div class="text-center py-12 text-surface-500">
		<p class="text-sm mb-3">This folder is empty</p>
		<button class="btn-secondary text-sm" onclick={goUp}>
			<svg class="w-4 h-4 inline-block mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
			</svg>
			Go back
		</button>
	</div>
{:else}
	<!-- Back button when in subfolder -->
	{#if $currentPath}
		<button
			class="flex items-center gap-2 mb-3 px-3 py-2 rounded-lg text-sm text-surface-400 hover:bg-surface-800 hover:text-surface-200 transition-colors w-full text-left"
			onclick={goUp}
		>
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
			</svg>
			..
		</button>
	{/if}

	<!-- Folders -->
	{#if filteredFolders().length > 0}
		<div class="space-y-1 mb-3">
			{#each filteredFolders() as folder}
				<div class="flex items-center gap-3 card !py-2.5 cursor-pointer hover:border-accent/30 group">
					<button
						class="flex items-center gap-3 flex-1 min-w-0 text-left"
						onclick={() => navigateToFolder(folder.path)}
					>
						<div class="w-10 h-10 bg-amber-500/10 rounded-lg flex items-center justify-center shrink-0">
							<svg class="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
							</svg>
						</div>
						<div class="min-w-0">
							<p class="text-surface-100 font-medium truncate">{folder.name}</p>
							<p class="text-xs text-surface-500">{folder.fileCount} file{folder.fileCount !== 1 ? 's' : ''}</p>
						</div>
					</button>
					<button
						class="btn-icon p-1.5 opacity-0 group-hover:opacity-100 text-red-400/50 hover:text-red-400 transition-all"
						onclick={() => deleteFolder(folder)}
						title="Delete folder (must be empty)"
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
						</svg>
					</button>
				</div>
			{/each}
		</div>
	{/if}

	<!-- Files: search empty state -->
	{#if searchQuery && filteredFiles().length === 0 && filteredFolders().length === 0}
		<div class="text-center py-12 text-surface-500">
			<p class="text-sm">No results for "{searchQuery}"</p>
			<button class="text-xs text-accent hover:text-accent-hover mt-2" onclick={() => searchQuery = ''}>
				Clear search
			</button>
		</div>
	{:else if viewMode === 'list'}
		<!-- List view -->
		<div class="space-y-2">
			{#each filteredFiles() as file}
				<div class="card {expandedFile === file.path ? 'ring-1 ring-accent/30' : ''}">
					<div class="flex items-center gap-3">
						{#if selectMode}
							<button
								class="w-5 h-5 rounded border flex items-center justify-center shrink-0 transition-colors
									   {selectedFiles.has(file.path) ? 'bg-accent border-accent' : 'border-surface-600 hover:border-surface-400'}"
								onclick={() => toggleSelect(file.path)}
							>
								{#if selectedFiles.has(file.path)}
									<svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
									</svg>
								{/if}
							</button>
						{/if}

						<button
							class="w-10 h-10 bg-surface-800 rounded-lg flex items-center justify-center shrink-0 hover:bg-surface-700 transition-colors"
							onclick={() => toggleExpand(file.path)}
							title="Show details"
						>
							<svg class="w-5 h-5 text-surface-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
							</svg>
						</button>

						<div class="flex-1 min-w-0">
							<p class="text-surface-100 font-medium truncate">{file.filename}</p>
							<div class="flex gap-3 text-xs text-surface-500 mt-0.5">
								<span>{formatFileSize(file.fileSize)}</span>
								{#if file.estimatedTime}
									<span>{formatDuration(file.estimatedTime)}</span>
								{/if}
								{#if file.layerCount}
									<span>{file.layerCount} layers</span>
								{/if}
								{#if file.estimatedCost}
									<span class="text-emerald-400">${file.estimatedCost.toFixed(2)}</span>
								{/if}
								{#if file.slicer}
									<span class="hidden sm:inline">{file.slicer}</span>
								{/if}
							</div>
						</div>

						<div class="flex gap-1 shrink-0">
							<button
								class="btn-primary text-sm px-3 py-1.5 inline-flex items-center gap-1.5"
								onclick={() => startPrint(file)}
								disabled={!isConnected || isPrinting || !!loading}
								title={!isConnected ? 'Printer not connected' : isPrinting ? 'A print is already in progress' : 'Print & monitor'}
							>
								{#if loading === 'print:' + file.path}
									<span class="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white/30 border-t-white"></span>
								{:else}
									<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
									</svg>
								{/if}
								Print
							</button>
							<button
								class="btn-icon text-red-400 hover:text-red-300 hover:bg-red-500/10"
								onclick={() => deleteFile(file)}
								disabled={!!loading}
								title="Delete file"
							>
								{#if loading === 'delete:' + file.path}
									<span class="animate-spin rounded-full h-4 w-4 border-2 border-red-400/30 border-t-red-400"></span>
								{:else}
									<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
									</svg>
								{/if}
							</button>
						</div>
					</div>

					{#if expandedFile === file.path}
						<div class="mt-3 pt-3 border-t border-surface-700 grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
							<div><span class="text-xs text-surface-500">File Size</span><p class="text-surface-300">{formatFileSize(file.fileSize)}</p></div>
							<div><span class="text-xs text-surface-500">Total Lines</span><p class="text-surface-300 tabular-nums">{file.totalLines.toLocaleString()}</p></div>
							<div><span class="text-xs text-surface-500">Printable Lines</span><p class="text-surface-300 tabular-nums">{file.printableLines.toLocaleString()}</p></div>
							{#if file.estimatedTime}<div><span class="text-xs text-surface-500">Est. Time</span><p class="text-surface-300">{formatDuration(file.estimatedTime)}</p></div>{/if}
							{#if file.layerCount}<div><span class="text-xs text-surface-500">Layers</span><p class="text-surface-300 tabular-nums">{file.layerCount}</p></div>{/if}
							{#if file.filamentUsedMm}<div><span class="text-xs text-surface-500">Filament</span><p class="text-surface-300">{(file.filamentUsedMm / 1000).toFixed(1)} m</p></div>{/if}
							{#if file.estimatedCost}<div><span class="text-xs text-surface-500">Est. Cost</span><p class="text-emerald-400">${file.estimatedCost.toFixed(2)}</p></div>{/if}
							{#if file.slicer}<div><span class="text-xs text-surface-500">Slicer</span><p class="text-surface-300">{file.slicer}</p></div>{/if}
							{#if file.nozzleTemp}<div><span class="text-xs text-surface-500">Nozzle Temp</span><p class="text-surface-300 tabular-nums">{file.nozzleTemp}°C</p></div>{/if}
							{#if file.bedTemp}<div><span class="text-xs text-surface-500">Bed Temp</span><p class="text-surface-300 tabular-nums">{file.bedTemp}°C</p></div>{/if}
							<div><span class="text-xs text-surface-500">Path</span><p class="text-surface-300 truncate text-xs">{file.path}</p></div>
						</div>
					{/if}
				</div>
			{/each}
		</div>
	{:else}
		<!-- Grid view -->
		<div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
			{#each filteredFiles() as file}
				<div class="card flex flex-col">
					<div class="w-full aspect-square bg-surface-800 rounded-lg flex items-center justify-center mb-3 relative">
						<svg class="w-10 h-10 text-surface-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
						</svg>
						{#if selectMode}
							<button
								class="absolute top-2 left-2 w-5 h-5 rounded border flex items-center justify-center transition-colors
									   {selectedFiles.has(file.path) ? 'bg-accent border-accent' : 'border-surface-600 bg-surface-900/80 hover:border-surface-400'}"
								onclick={() => toggleSelect(file.path)}
							>
								{#if selectedFiles.has(file.path)}
									<svg class="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
									</svg>
								{/if}
							</button>
						{/if}
						{#if file.estimatedTime}
							<span class="absolute bottom-2 right-2 text-xs bg-surface-900/80 text-surface-300 px-1.5 py-0.5 rounded">
								{formatDuration(file.estimatedTime)}
							</span>
						{/if}
					</div>
					<p class="text-sm text-surface-200 font-medium truncate mb-1" title={file.filename}>{file.filename}</p>
					<p class="text-xs text-surface-500 mb-3">{formatFileSize(file.fileSize)}</p>
					<div class="flex gap-1 mt-auto">
						<button
							class="btn-primary text-xs px-2.5 py-1.5 flex-1"
							onclick={() => startPrint(file)}
							disabled={!isConnected || isPrinting || !!loading}
						>
							Print
						</button>
						<button
							class="btn-icon text-red-400 hover:text-red-300 hover:bg-red-500/10"
							onclick={() => deleteFile(file)}
							disabled={!!loading}
							title="Delete"
						>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
							</svg>
						</button>
					</div>
				</div>
			{/each}
		</div>
	{/if}
{/if}
