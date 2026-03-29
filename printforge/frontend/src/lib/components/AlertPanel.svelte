<script lang="ts">
	import { activeErrors, activeErrorCount, dismissErrorLocal, dismissAllLocal, type ErrorEntry } from '$lib/stores/errors';
	import { api } from '$lib/api';

	let expanded = $state<number | null>(null);
	let dismissing = $state<number | null>(null);

	let errors = $derived($activeErrors);
	let count = $derived($activeErrorCount);

	const severityConfig: Record<string, { bg: string; border: string; text: string; icon: string; badge: string }> = {
		critical: {
			bg: 'bg-red-500/10',
			border: 'border-red-500/25',
			text: 'text-red-400',
			icon: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z',
			badge: 'bg-red-500/20 text-red-400'
		},
		error: {
			bg: 'bg-orange-500/10',
			border: 'border-orange-500/25',
			text: 'text-orange-400',
			icon: 'M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
			badge: 'bg-orange-500/20 text-orange-400'
		},
		warning: {
			bg: 'bg-amber-500/10',
			border: 'border-amber-500/25',
			text: 'text-amber-400',
			icon: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z',
			badge: 'bg-amber-500/20 text-amber-400'
		},
		info: {
			bg: 'bg-blue-500/10',
			border: 'border-blue-500/25',
			text: 'text-blue-400',
			icon: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
			badge: 'bg-blue-500/20 text-blue-400'
		}
	};

	const categoryLabels: Record<string, string> = {
		serial: 'Serial',
		temperature: 'Temperature',
		mechanical: 'Mechanical',
		firmware: 'Firmware',
		print: 'Print',
		safety: 'Safety',
		system: 'System'
	};

	function getConfig(severity: string) {
		return severityConfig[severity] || severityConfig.warning;
	}

	function formatTime(timestamp: number): string {
		const date = new Date(timestamp * 1000);
		const now = new Date();
		const diff = Math.floor((now.getTime() - date.getTime()) / 1000);

		if (diff < 60) return 'just now';
		if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
		if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
		return date.toLocaleDateString();
	}

	function toggle(id: number) {
		expanded = expanded === id ? null : id;
	}

	async function dismiss(e: MouseEvent, id: number) {
		e.stopPropagation();
		dismissing = id;
		dismissErrorLocal(id);
		try {
			await api.dismissError(id);
		} catch {
			// Already dismissed locally
		}
		dismissing = null;
	}

	async function dismissAll() {
		dismissAllLocal();
		try {
			await api.dismissAllErrors();
		} catch {
			// Already dismissed locally
		}
	}
</script>

{#if count > 0}
	<div class="card !p-0 overflow-hidden border-red-500/20">
		<!-- Header -->
		<div class="flex items-center justify-between px-4 py-3 bg-red-500/5 border-b border-surface-700/50">
			<div class="flex items-center gap-2">
				<div class="w-6 h-6 rounded-lg bg-red-500/15 flex items-center justify-center">
					<svg class="w-3.5 h-3.5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
					</svg>
				</div>
				<h3 class="text-sm font-semibold text-surface-200">
					Alerts
				</h3>
				<span class="text-xs px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400 tabular-nums font-medium">
					{count}
				</span>
			</div>
			{#if count > 1}
				<button
					class="text-xs text-surface-500 hover:text-surface-300 transition-colors"
					onclick={dismissAll}
				>
					Dismiss all
				</button>
			{/if}
		</div>

		<!-- Error list -->
		<div class="divide-y divide-surface-800/50">
			{#each errors as error (error.id)}
				{@const config = getConfig(error.severity)}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<!-- svelte-ignore a11y_click_events_have_key_events -->
				<div class="group" role="listitem">
					<!-- Error row -->
					<div
						class="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-surface-800/30 transition-colors cursor-pointer select-none"
						onclick={() => toggle(error.id)}
					>
						<!-- Severity icon -->
						<div class="mt-0.5 shrink-0">
							<svg class="w-4 h-4 {config.text}" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d={config.icon} />
							</svg>
						</div>

						<!-- Content -->
						<div class="flex-1 min-w-0">
							<div class="flex items-center gap-2 mb-0.5">
								<span class="text-sm font-medium text-surface-200 truncate">{error.title}</span>
								<span class="text-[10px] px-1.5 py-0.5 rounded {config.badge} uppercase font-semibold tracking-wide shrink-0">
									{error.severity}
								</span>
								<span class="text-[10px] px-1.5 py-0.5 rounded bg-surface-700/50 text-surface-500 shrink-0">
									{categoryLabels[error.category] || error.category}
								</span>
							</div>
							<p class="text-xs text-surface-400 truncate">{error.message}</p>
							<span class="text-[10px] text-surface-600 mt-0.5 block">{formatTime(error.timestamp)}</span>
						</div>

						<!-- Actions -->
						<div class="flex items-center gap-1 shrink-0 mt-0.5">
							<!-- Dismiss button -->
							<button
								class="p-1 rounded hover:bg-surface-700 text-surface-600 hover:text-surface-300 transition-colors opacity-0 group-hover:opacity-100"
								onclick={(e) => dismiss(e, error.id)}
								title="Dismiss"
							>
								<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
								</svg>
							</button>
							<!-- Expand chevron -->
							<svg
								class="w-4 h-4 text-surface-600 transition-transform duration-200 {expanded === error.id ? 'rotate-180' : ''}"
								fill="none" stroke="currentColor" viewBox="0 0 24 24"
							>
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
							</svg>
						</div>
					</div>

					<!-- Expanded details -->
					{#if expanded === error.id}
						<div class="px-4 pb-4 pt-1 ml-7 space-y-3 {config.bg} border-t {config.border}">
							<!-- Description -->
							<div>
								<h4 class="text-xs font-semibold text-surface-300 mb-1">What happened</h4>
								<p class="text-xs text-surface-400 leading-relaxed">{error.description}</p>
							</div>

							<!-- Suggested fixes -->
							{#if error.fixes.length > 0}
								<div>
									<h4 class="text-xs font-semibold text-surface-300 mb-1.5">Suggested fixes</h4>
									<ul class="space-y-1.5">
										{#each error.fixes as fix, i}
											<li class="flex items-start gap-2 text-xs text-surface-400">
												<span class="w-4 h-4 rounded-full bg-surface-700/80 text-surface-500 flex items-center justify-center shrink-0 text-[10px] font-medium mt-0.5">
													{i + 1}
												</span>
												<span class="leading-relaxed">{fix}</span>
											</li>
										{/each}
									</ul>
								</div>
							{/if}

							<!-- Raw message -->
							{#if error.raw && error.raw !== error.message}
								<div>
									<h4 class="text-xs font-semibold text-surface-300 mb-1">Raw output</h4>
									<code class="text-[10px] text-surface-500 bg-surface-900/50 rounded px-2 py-1 block font-mono break-all">
										{error.raw}
									</code>
								</div>
							{/if}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	</div>
{/if}
