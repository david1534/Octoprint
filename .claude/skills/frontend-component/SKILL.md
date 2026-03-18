---
name: frontend-component
description: Build a new Svelte 5 component following PrintForge's exact design system, dark theme, and patterns. Use when the user asks to create, add, or build a new UI component, widget, card, modal, gauge, or interactive element.
argument-hint: <ComponentName> <description>
allowed-tools: Read, Grep, Glob, Bash, Write, Edit, Task
---

# PrintForge Frontend Component Builder

Build a new Svelte 5 component that matches PrintForge's dark-themed industrial design system exactly.

## Steps

1. Parse `$ARGUMENTS`:
   - First word = ComponentName in **PascalCase** (e.g. `FilamentSwatch`, `BedLevelIndicator`)
   - Remaining words = description
   - If missing, ask the user

2. **Research before writing.** Read these files:
   - `printforge/frontend/src/app.css` -- component classes, animations
   - `printforge/frontend/tailwind.config.js` -- color palette
   - `printforge/frontend/src/lib/stores/` -- available stores
   - `printforge/frontend/src/lib/api.ts` -- API methods
   - Existing components in `printforge/frontend/src/lib/components/` for patterns

3. **Write the component** to `printforge/frontend/src/lib/components/<ComponentName>.svelte`

4. **Verify** the build: `cd printforge/frontend && bun run build`

## Design System Reference

### Theme: Dark-First Industrial

PrintForge is a **dark-only** app. All surfaces use the `surface-*` scale against a near-black background.

### Color Palette (Tailwind classes)
```
Page background:    bg-surface-950  (#020617)
Card/sidebar:       bg-surface-900  (#0f172a)
Input background:   bg-surface-800  (#1e293b)
Hover states:       bg-surface-800 or bg-surface-700
Card borders:       border-surface-700  (#334155)
Input borders:      border-surface-600  (#475569)
Muted text:         text-surface-500  (#64748b)
Secondary text:     text-surface-400  (#94a3b8)
Headings:           text-surface-300  (#cbd5e1)
Emphasized text:    text-surface-200  (#e2e8f0)
Body text:          text-surface-100  (#f1f5f9)

Primary accent:     bg-accent (#3b82f6) / text-accent / hover:bg-accent-hover (#2563eb)
Danger:             bg-red-600 / text-red-400  / hover:bg-red-700
Success:            bg-emerald-600 / text-emerald-400 / hover:bg-emerald-700
Warning:            bg-amber-500 / text-amber-400
Hotend temp:        text-orange-400 (#f97316)
Bed temp:           text-blue-400 (#3b82f6)
```

### Component CSS Classes (from app.css)
```css
.card        -- bg-surface-900 border border-surface-700 rounded-xl p-4 + hover shadow
.btn         -- px-4 py-2 rounded-lg font-medium transition-colors duration-150
.btn-primary -- btn + bg-accent text-white hover:bg-accent-hover
.btn-secondary -- btn + bg-surface-700 text-surface-100 hover:bg-surface-600
.btn-danger  -- btn + bg-red-600 text-white hover:bg-red-700
.btn-success -- btn + bg-emerald-600 text-white hover:bg-emerald-700
.btn-icon    -- p-2 rounded-lg hover:bg-surface-700 text-surface-400 hover:text-surface-100
.input       -- bg-surface-800 border-surface-600 rounded-lg px-3 py-2 + focus:ring-accent/50
.badge       -- inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium
```

### Svelte 5 Patterns (CRITICAL -- this project uses runes)
```svelte
<script lang="ts">
  // Props -- use $props() rune, NOT export let
  let { label, value = 0, onchange }: {
    label: string;
    value?: number;
    onchange?: (v: number) => void;
  } = $props();

  // State -- use $state rune
  let count = $state(0);
  let items = $state<string[]>([]);

  // Derived -- use $derived rune
  let doubled = $derived(count * 2);

  // Effects -- use $effect rune
  $effect(() => {
    console.log('count changed:', count);
  });

  // Bindable props -- use $bindable()
  let { open = $bindable(false) } = $props();

  // Event handlers -- use onclick, NOT on:click
  function handleClick() { count++; }
</script>

<!-- Use onclick, NOT on:click -->
<button onclick={handleClick}>Click</button>

<!-- Children -- use {@render children()} NOT <slot> -->
{@render children()}
```

### Icon Pattern
Inline SVGs from Heroicons (outline, stroke-based):
```svelte
<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="..." />
</svg>
```

### Card Pattern
```svelte
<div class="card">
  <h3 class="text-sm font-semibold text-surface-300 mb-3 flex items-center gap-2">
    <svg class="w-4 h-4 text-surface-400" ...>...</svg>
    Section Title
  </h3>
  <!-- Content -->
</div>
```

### Loading Spinner
```svelte
<span class="animate-spin rounded-full h-4 w-4 border-2 border-surface-400 border-t-white"></span>
```

### Focus States
Always add for keyboard accessibility:
```
focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/50
```

### Touch Targets
All interactive elements on control pages need minimum height:
```
min-h-[44px]
```

## Stores Available
```typescript
import { printerState, isConnected, isPrinting, isPaused } from '$lib/stores/printer';
import { temperatureHistory } from '$lib/stores/temperature';
import { terminalLines } from '$lib/stores/terminal';
import { toast } from '$lib/stores/toast';           // toast.success(), .error(), .warning(), .info()
import { confirmAction } from '$lib/stores/confirm';  // await confirmAction({title, message, variant})
import { files, refreshFiles } from '$lib/stores/files';
```

### API Access
```typescript
import { api } from '$lib/api';
// 50+ typed methods: api.connect(), api.home(), api.jog(), api.setTemp(), etc.
```

## Critical Rules

- **ALWAYS** use Svelte 5 runes (`$state`, `$derived`, `$effect`, `$props`) -- NEVER `export let` or `on:event`
- **ALWAYS** use `onclick` not `on:click`, `onchange` not `on:change`, etc.
- **ALWAYS** use `{@render children()}` not `<slot>`
- **NEVER** use light theme colors -- this is a dark-only app
- **ALWAYS** use Tailwind utility classes -- never inline `style=` unless dynamic values are needed
- **ALWAYS** add `focus-visible` rings on interactive elements
- **ALWAYS** include `transition-colors duration-150` on interactive elements
- **NEVER** install new dependencies without asking the user
- Use `tabular-nums` class for any numerical displays (temps, positions, times)
