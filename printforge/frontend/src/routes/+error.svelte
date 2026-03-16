<script lang="ts">
	import { page } from '$app/stores';
</script>

<svelte:head>
	<title>PrintForge - Error</title>
</svelte:head>

<div class="flex flex-col items-center justify-center min-h-[60vh] text-center px-4">
	<div class="mb-6">
		<svg class="w-16 h-16 text-surface-600 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
			<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
		</svg>
	</div>

	<h1 class="text-4xl font-bold text-surface-200 mb-2 tabular-nums">{$page.status}</h1>
	<p class="text-lg text-surface-400 mb-6 max-w-md">
		{$page.error?.message || 'Something went wrong'}
	</p>

	<div class="flex gap-3">
		<a
			href="/"
			class="btn-primary inline-flex items-center gap-2
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
		>
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
			</svg>
			Dashboard
		</a>
		<button
			class="btn-secondary inline-flex items-center gap-2
				   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50"
			onclick={() => window.location.reload()}
		>
			<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
			</svg>
			Retry
		</button>
	</div>
</div>
