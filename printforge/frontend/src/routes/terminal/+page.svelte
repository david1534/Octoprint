<script lang="ts">
	import Terminal from '$lib/components/Terminal.svelte';
</script>

<svelte:head>
	<title>PrintForge - Terminal</title>
</svelte:head>

<h1 class="text-xl font-bold mb-4">G-code Terminal</h1>

<div class="h-[calc(100vh-12rem)]">
	<Terminal />
</div>
