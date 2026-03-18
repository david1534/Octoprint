---
name: frontend-page
description: Add a new page (route) to the PrintForge frontend. Use when the user asks to create a new page, screen, view, or tab. Handles SvelteKit file-based routing, layout integration, and navigation link.
argument-hint: <page-name> <description>
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, Task
---

# PrintForge Page Builder

Add a complete new page to PrintForge -- SvelteKit route, navigation link (sidebar + mobile bottom nav), and page component.

## Steps

1. Parse `$ARGUMENTS`:
   - First word = page name in **kebab-case** (e.g. `analytics`, `webcam-settings`)
   - Remaining words = description
   - If missing, ask the user

2. **Research before writing.** Read these files:
   - `printforge/frontend/src/routes/+layout.svelte` -- nav items array, layout structure
   - `printforge/frontend/src/routes/+page.svelte` -- dashboard pattern reference
   - `printforge/frontend/src/lib/api.ts` -- available API methods
   - `printforge/frontend/src/app.css` -- component classes

3. **Create the route** at `printforge/frontend/src/routes/<page-name>/+page.svelte`

4. **Add the nav link** in `printforge/frontend/src/routes/+layout.svelte`:
   Add an entry to the `navItems` array:
   ```typescript
   { path: '/page-name', label: 'Page Name', icon: 'M...' }
   ```
   Use a Heroicons path for the icon. Keep total nav items reasonable (8-9 max for mobile bottom bar).

5. **Add API client methods** if the page needs backend data (in `printforge/frontend/src/lib/api.ts`).

6. **Verify** the build: `cd printforge/frontend && bun run build`

## Page Template

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '$lib/api';
  import { toast } from '$lib/stores/toast';
  import { printerState, isConnected } from '$lib/stores/printer';

  let connected = $derived($isConnected);
  let loading = $state(true);
  let error = $state<string | null>(null);

  onMount(async () => {
    try {
      // Load data
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  });
</script>

<svelte:head>
  <title>PrintForge - Page Name</title>
</svelte:head>

<div class="space-y-4 fade-in">
  <div class="flex items-center justify-between">
    <h1 class="text-lg font-semibold text-surface-200">Page Title</h1>
  </div>

  {#if loading}
    <div class="card flex items-center justify-center py-12">
      <span class="animate-spin rounded-full h-6 w-6 border-2 border-surface-600 border-t-accent"></span>
    </div>
  {:else if error}
    <div class="card text-center py-8">
      <p class="text-red-400 text-sm">{error}</p>
    </div>
  {:else}
    <!-- Page content -->
  {/if}
</div>
```

## Routing Patterns

SvelteKit uses **file-based routing** at `src/routes/`:

| File path | URL | Notes |
|---|---|---|
| `routes/+page.svelte` | `/` | Dashboard |
| `routes/files/+page.svelte` | `/files` | Standard page |
| `routes/settings/+page.svelte` | `/settings` | Settings (uses tabs internally) |

All pages are nested inside `+layout.svelte` which provides the sidebar, top bar, and bottom nav.

## Navigation Array Pattern

In `+layout.svelte`, the `navItems` array drives both desktop sidebar and mobile bottom nav:

```typescript
const navItems = [
  { path: '/', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7...' },
  { path: '/control', label: 'Control', icon: 'M10.325 4.317...' },
  // ... add new entries here
];
```

Active state is determined by `currentPath.startsWith(item.path)` (except `/` which uses exact match).

## Critical Rules

- **ALWAYS** use Svelte 5 runes (`$state`, `$derived`, `$props`, `$effect`)
- **ALWAYS** add `<svelte:head>` with a `<title>` tag
- **ALWAYS** wrap page content in `<div class="space-y-4 fade-in">`
- **ALWAYS** add the nav link so users can navigate to the page
- **ALWAYS** handle loading, error, and empty states
- **NEVER** create a page without a navigation entry -- orphan routes are invisible to users
- **NEVER** add more than 9 nav items without discussing mobile bottom bar overflow
- Follow the `frontend-component` skill for all styling and Svelte 5 patterns
