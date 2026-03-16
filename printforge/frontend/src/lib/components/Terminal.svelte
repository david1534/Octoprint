<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { terminalLines, type TerminalLine } from '../stores/terminal';
	import { wsManager } from '../websocket';
	import { printerState } from '../stores/printer';
	import { toast } from '../stores/toast';

	let input = $state('');
	let searchQuery = $state('');
	let container: HTMLDivElement;
	let autoScroll = $state(true);
	let showSearch = $state(false);
	let isConnected = $derived($printerState.status !== 'disconnected');

	let history: string[] = [];
	let historyIndex = $state(-1);

	const quickCommands = [
		{ label: 'Home', cmd: 'G28', desc: 'Home all axes' },
		{ label: 'Z Up', cmd: 'G0 Z10 F600', desc: 'Move Z up 10mm' },
		{ label: 'Motors Off', cmd: 'M84', desc: 'Disable steppers' },
		{ label: 'Position', cmd: 'M114', desc: 'Report position' },
		{ label: 'Settings', cmd: 'M503', desc: 'Report settings' },
		{ label: 'Temps', cmd: 'M105', desc: 'Report temperatures' },
	];

	// Filter lines based on search
	let displayLines = $derived(() => {
		if (!searchQuery.trim()) return $terminalLines;
		const q = searchQuery.toLowerCase();
		return $terminalLines.filter(l => l.text.toLowerCase().includes(q));
	});

	$effect(() => {
		const _ = $terminalLines;
		if (autoScroll && container) {
			tick().then(() => {
				container.scrollTop = container.scrollHeight;
			});
		}
	});

	function sendCommand(cmd?: string) {
		const c = (cmd || input).trim();
		if (!c) return;
		wsManager.sendCommand(c);
		if (!cmd) {
			history = [c, ...history.slice(0, 49)];
			historyIndex = -1;
			input = '';
		}
	}

	function onKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			sendCommand();
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			if (historyIndex < history.length - 1) {
				historyIndex++;
				input = history[historyIndex];
			}
		} else if (e.key === 'ArrowDown') {
			e.preventDefault();
			if (historyIndex > 0) {
				historyIndex--;
				input = history[historyIndex];
			} else {
				historyIndex = -1;
				input = '';
			}
		}
	}

	function copyAll() {
		const text = $terminalLines
			.map(l => `${linePrefix(l.direction)}${l.text}`)
			.join('\n');
		navigator.clipboard.writeText(text).then(() => {
			toast.info('Terminal output copied');
		}).catch(() => {
			toast.error('Failed to copy');
		});
	}

	function clearTerminal() {
		terminalLines.set([]);
	}

	function lineColor(direction: string): string {
		switch (direction) {
			case 'send': return 'text-emerald-400';
			case 'recv': return 'text-surface-300';
			case 'system': return 'text-amber-400';
			default: return 'text-surface-400';
		}
	}

	function linePrefix(direction: string): string {
		switch (direction) {
			case 'send': return '>>> ';
			case 'recv': return '<<< ';
			case 'system': return '[!] ';
			default: return '';
		}
	}

	function highlightMatch(text: string): string {
		if (!searchQuery.trim()) return text;
		const q = searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
		return text.replace(new RegExp(`(${q})`, 'gi'), '<mark class="bg-amber-500/30 text-amber-200 rounded px-0.5">$1</mark>');
	}
</script>

<div class="card flex flex-col h-full">
	<!-- Disconnected indicator -->
	{#if !isConnected}
		<div class="bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2 mb-2 text-xs text-amber-400 flex items-center gap-2">
			<svg class="w-4 h-4 shrink-0 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 5.636a9 9 0 010 12.728m-2.829-2.829a5 5 0 000-7.07m-4.243 9.9a9 9 0 01-4.243-2.829m2.829-2.829a5 5 0 010-7.07" />
			</svg>
			Printer disconnected — commands will be unavailable until reconnected
		</div>
	{/if}

	<!-- Header with actions -->
	<div class="flex items-center justify-between mb-2 gap-2">
		<h3 class="text-sm font-medium text-surface-400">Terminal</h3>
		<div class="flex items-center gap-1">
			<button
				class="btn-icon p-1.5"
				onclick={() => showSearch = !showSearch}
				title="Search"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
				</svg>
			</button>
			<button
				class="btn-icon p-1.5"
				onclick={copyAll}
				title="Copy all"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
				</svg>
			</button>
			<button
				class="btn-icon p-1.5"
				onclick={clearTerminal}
				title="Clear"
			>
				<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
				</svg>
			</button>
			<label class="flex items-center gap-1.5 text-xs text-surface-500 ml-2">
				<input type="checkbox" bind:checked={autoScroll} class="accent-accent" />
				Auto-scroll
			</label>
		</div>
	</div>

	<!-- Search bar -->
	{#if showSearch}
		<div class="relative mb-2">
			<svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-surface-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
			</svg>
			<input
				type="text"
				class="input w-full text-xs pl-8 py-1.5 font-mono"
				placeholder="Filter output..."
				bind:value={searchQuery}
			/>
			{#if searchQuery}
				<span class="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-surface-500">
					{displayLines().length} matches
				</span>
			{/if}
		</div>
	{/if}

	<!-- Quick command buttons -->
	<div class="flex gap-1 mb-2 overflow-x-auto pb-1">
		{#each quickCommands as qc}
			<button
				class="px-2.5 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors
					   bg-surface-800/50 text-surface-400 hover:bg-surface-800 hover:text-surface-200
					   disabled:opacity-50 disabled:cursor-not-allowed
					   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
				onclick={() => sendCommand(qc.cmd)}
				disabled={!isConnected}
				title={qc.desc}
			>
				{qc.label}
			</button>
		{/each}
	</div>

	<!-- Terminal output -->
	<div
		bind:this={container}
		class="flex-1 bg-surface-950 rounded-lg p-3 font-mono text-xs overflow-y-auto min-h-[200px] max-h-[600px]"
	>
		{#each displayLines() as line}
			<div class={lineColor(line.direction)}>
				<span class="opacity-50 select-none">{linePrefix(line.direction)}</span>{@html highlightMatch(line.text)}
			</div>
		{/each}
		{#if $terminalLines.length === 0}
			<div class="text-surface-600 italic">Waiting for output...</div>
		{/if}
	</div>

	<!-- Input -->
	<div class="flex gap-2 mt-2">
		<input
			type="text"
			class="input flex-1 font-mono text-sm"
			placeholder="G-code command (e.g. G28)"
			bind:value={input}
			onkeydown={onKeydown}
			disabled={!isConnected}
		/>
		<button
			class="btn-primary min-h-[40px]
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={() => sendCommand()}
			disabled={!isConnected || !input.trim()}
		>
			Send
		</button>
	</div>
</div>
