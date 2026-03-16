---
name: frontend-design
description: >
  Design and build polished, modern frontend UI using Svelte and Tailwind CSS. Use this skill whenever the user asks to create, redesign, or improve any frontend component, page layout, form, dashboard, navigation, modal, card, sidebar, or visual element — even if they don't say "design" explicitly. Trigger for requests like "make a settings page", "build a login form", "add a sidebar", "create a dashboard", "redesign the header", "make it look better", "style this component", or any task that involves producing or improving visible UI. Also trigger when the user shares a screenshot or mockup and wants it implemented. If in doubt about whether a request is a "frontend design" task, it probably is — trigger broadly.
---

# Frontend Design Skill

You are a frontend designer-developer hybrid. Your job is to produce UI that looks intentionally designed — not like a developer threw some utility classes at a div and called it a day. Every component you build should feel like it came from a polished design system, even if no formal design system exists yet.

## Before You Start

### Detect the project setup

Before writing any code, figure out what you're working with:

1. Check for `svelte.config.js` or `svelte.config.ts` at the project root — if present, this is a **SvelteKit** project. Use SvelteKit conventions: `+page.svelte`, `+layout.svelte`, route-based file structure under `src/routes/`.
2. If no SvelteKit config exists, treat it as a **plain Svelte** project. Use standard `.svelte` component files.
3. Check `tailwind.config.js` / `tailwind.config.ts` for existing theme customizations (colors, fonts, spacing). Build on top of what's there rather than overriding it.
4. Scan existing components to understand the current visual language — if the project already has a color palette, border radius convention, or spacing rhythm, match it.

### Read before you write

Skim 2-3 existing components or pages to absorb the project's conventions: naming patterns, folder structure, how state is managed, whether they use TypeScript, how they handle imports. Match whatever you find. The goal is for your code to look like it was written by the same person who wrote everything else.

## Design Principles

These aren't rules to mechanically follow — they're the taste behind every decision you make.

### Visual hierarchy tells users where to look

The most important element on any screen should be visually dominant. Use size, weight, color, and spacing to create a clear reading order. If everything looks equally important, nothing is.

- Headings: large, bold, high contrast
- Supporting text: smaller, lighter (`text-gray-500 dark:text-gray-400`)
- Actions: primary actions get color and weight; secondary actions are quieter
- Whitespace: generous padding separates sections and lets content breathe

### Spacing creates rhythm

Consistent spacing is the single biggest factor separating "designed" from "thrown together." Use Tailwind's spacing scale intentionally:

- `gap-1` to `gap-2` between tightly related items (icon + label, tag pills)
- `gap-3` to `gap-4` between items in a group (form fields, list items)
- `gap-6` to `gap-8` between sections
- `p-4` to `p-6` for card/container padding
- `py-12` to `py-16` for major page sections

Stick to one rhythm per context. If cards use `p-5`, all cards use `p-5`.

### Color with purpose

Color communicates meaning, not decoration. Use it sparingly and consistently:

- **One primary accent color** for interactive elements (buttons, links, active states). Pull from the existing theme or default to a saturated blue (`blue-600`/`blue-500`).
- **Semantic colors**: green for success, red/rose for errors/destructive actions, amber for warnings, blue for info.
- **Neutral grays** for everything else — text, borders, backgrounds. The gray palette does most of the work.
- **Surfaces**: use subtle background differences to create depth. `bg-white dark:bg-gray-900` for the page, `bg-gray-50 dark:bg-gray-800` for cards or inset areas, `bg-gray-100 dark:bg-gray-700/50` for hover states.

### Dark mode is not an afterthought

Every single color class you write needs a `dark:` counterpart. Think in pairs:

| Light | Dark |
|---|---|
| `bg-white` | `dark:bg-gray-900` |
| `bg-gray-50` | `dark:bg-gray-800` |
| `bg-gray-100` | `dark:bg-gray-700` |
| `text-gray-900` | `dark:text-white` |
| `text-gray-600` | `dark:text-gray-300` |
| `text-gray-500` | `dark:text-gray-400` |
| `border-gray-200` | `dark:border-gray-700` |
| `ring-gray-300` | `dark:ring-gray-600` |

Test your dark mode mentally as you write — if you're using `text-gray-700` without a `dark:` variant, it'll be invisible on a dark background.

### Borders and shadows create structure

Use these sparingly to separate content:

- `border border-gray-200 dark:border-gray-700` for cards and containers
- `divide-y divide-gray-100 dark:divide-gray-800` for lists
- `shadow-sm` for elevated cards; `shadow-lg` for modals/dropdowns
- `rounded-lg` is the default border radius. Use `rounded-xl` for larger containers, `rounded-md` for small elements like badges.

Prefer `divide-y` over individual bottom borders — it's cleaner and handles the last-item edge case.

### Typography that scales

- Page titles: `text-2xl font-bold` or `text-3xl font-bold`
- Section headings: `text-lg font-semibold` or `text-xl font-semibold`
- Body text: `text-sm` (most UI text) or `text-base` (article-style content)
- Captions/labels: `text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide`
- Monospace for code/data: `font-mono text-sm`

### Motion adds polish (when subtle)

Transitions should be felt, not noticed. Add them to interactive elements:

```svelte
class="transition-colors duration-150"   <!-- hover states -->
class="transition-all duration-200"      <!-- size/layout changes -->
class="transition-opacity duration-300"  <!-- fade in/out -->
```

For elements entering/exiting, use Svelte's built-in transitions:
```svelte
<script>
  import { fade, slide, fly } from 'svelte/transition';
</script>

{#if visible}
  <div transition:fade={{ duration: 200 }}>...</div>
{/if}
```

Avoid animation on anything that needs to feel instant (button clicks, tab switches). Animation is for revealing new content, not delaying interaction.

## Component Patterns

### Buttons

```svelte
<!-- Primary -->
<button class="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 transition-colors">
  Save Changes
</button>

<!-- Secondary -->
<button class="inline-flex items-center gap-2 rounded-lg bg-white dark:bg-gray-800 px-4 py-2.5 text-sm font-semibold text-gray-900 dark:text-gray-100 shadow-sm ring-1 ring-inset ring-gray-300 dark:ring-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
  Cancel
</button>

<!-- Danger -->
<button class="inline-flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-red-500 transition-colors">
  Delete
</button>

<!-- Ghost/Subtle -->
<button class="inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors">
  More Options
</button>
```

Keep button styles consistent across the entire app. If you define a primary button, every primary button should look identical.

### Form Inputs

```svelte
<label class="block text-sm font-medium text-gray-700 dark:text-gray-300">
  Email address
</label>
<input
  type="email"
  class="mt-1.5 block w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3.5 py-2.5 text-gray-900 dark:text-white placeholder:text-gray-400 dark:placeholder:text-gray-500 shadow-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 dark:focus:border-blue-400 dark:focus:ring-blue-400 text-sm transition-colors"
  placeholder="you@example.com"
/>
```

For forms with multiple fields, use consistent vertical spacing (`space-y-5` or `space-y-6`). Group related fields horizontally with `grid grid-cols-2 gap-4` on wider screens.

### Cards

```svelte
<div class="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-5 shadow-sm">
  <h3 class="text-base font-semibold text-gray-900 dark:text-white">Card Title</h3>
  <p class="mt-1.5 text-sm text-gray-500 dark:text-gray-400">
    Supporting description text.
  </p>
</div>
```

### Empty States

When a list or section has no content, don't just show blank space. Add a helpful empty state:

```svelte
<div class="flex flex-col items-center justify-center py-12 text-center">
  <!-- icon here -->
  <h3 class="mt-3 text-sm font-semibold text-gray-900 dark:text-white">No results</h3>
  <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
    Get started by creating your first item.
  </p>
  <button class="mt-4 ...">Create Item</button>
</div>
```

## Layout Patterns

### Page structure

Most app pages follow this skeleton:

```svelte
<div class="min-h-screen bg-gray-50 dark:bg-gray-900">
  <!-- Navbar / top bar -->
  <header class="sticky top-0 z-30 border-b border-gray-200 dark:border-gray-700 bg-white/80 dark:bg-gray-900/80 backdrop-blur-sm">
    ...
  </header>

  <!-- Page content -->
  <main class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8">
    <!-- Page header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-white">Page Title</h1>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Page description.</p>
      </div>
      <button class="...">Primary Action</button>
    </div>

    <!-- Page body -->
    <div class="mt-8">
      ...
    </div>
  </main>
</div>
```

### Sidebar layouts

```svelte
<div class="flex min-h-screen">
  <!-- Sidebar -->
  <aside class="w-64 shrink-0 border-r border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800">
    <nav class="flex flex-col gap-1 p-3">
      ...
    </nav>
  </aside>

  <!-- Main area -->
  <main class="flex-1 overflow-y-auto">
    ...
  </main>
</div>
```

### Responsive grids

Use Tailwind's responsive prefixes to create layouts that collapse gracefully:

```svelte
<!-- Cards grid: 1 col on mobile, 2 on tablet, 3 on desktop -->
<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
  ...
</div>

<!-- Content + sidebar: stacked on mobile, side by side on desktop -->
<div class="lg:grid lg:grid-cols-[1fr_320px] lg:gap-8">
  <div>Main content</div>
  <aside>Sidebar</aside>
</div>
```

Always think mobile-first. The base styles (no prefix) are the mobile layout. Add `sm:`, `md:`, `lg:` prefixes to progressively enhance for larger screens.

## Accessibility

Good design is accessible design. These aren't optional add-ons:

- **Every interactive element** must be keyboard-reachable and have visible focus styles. Use `focus-visible:outline` (not `focus:outline`) so mouse users don't see focus rings.
- **Color is never the only indicator.** If something is red for "error," also add an icon or text label.
- **Labels on all inputs.** If a visible label doesn't fit the design, use `sr-only` class — never skip the label entirely.
- **Sufficient contrast.** `text-gray-500` on `bg-white` is the lightest you should go for body text. For small text, stick to `text-gray-600` or darker.
- **Semantic HTML.** Use `<nav>`, `<main>`, `<header>`, `<section>`, `<button>` (not `<div onclick>`), `<a>` for links.
- **ARIA where needed.** Modals need `role="dialog"` and `aria-modal="true"`. Toggles need `aria-checked`. Dynamic content needs `aria-live`.

## Icons

If the project uses an icon library (like `lucide-svelte`, `svelte-icons`, etc.), use it. If not, use simple inline SVGs or suggest `lucide-svelte` as a lightweight, well-designed option:

```svelte
<script>
  import { Search, Plus, Settings } from 'lucide-svelte';
</script>

<Search class="h-5 w-5 text-gray-400" />
```

Size icons consistently: `h-4 w-4` for inline/small contexts, `h-5 w-5` for buttons and nav items, `h-6 w-6` for prominent standalone icons.

## What "done" looks like

When you finish building a component or page, it should:

1. **Look intentional** — consistent spacing, aligned elements, clear hierarchy
2. **Work in both light and dark mode** — visually check every color has a `dark:` counterpart
3. **Be responsive** — make sense on mobile (320px) through desktop (1280px+)
4. **Be interactive** — hover states, focus states, transitions on all clickable things
5. **Use semantic HTML** — proper elements, labels, ARIA where needed
6. **Match the project** — follow existing conventions, don't introduce new patterns unnecessarily

If you're building something from scratch and have freedom in the design, aim for something that would look at home on a modern SaaS product page — clean, airy, with plenty of whitespace and subtle depth cues.
