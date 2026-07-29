# Data Model: App shell, design tokens, component library, and PWA basics

This slice persists nothing to a database and calls no API — there is no domain data model.
The two "entities" from the spec's Key Entities section are configuration/UI-state shapes,
recorded here as the TypeScript types other tasks and future features will import.

## Theme preference

**Corrected by `docs/handoffs/001-app-shell-fix-theme.md` — this section previously described
a cookie-backed model; see `research.md`'s amended "Boot-time theme" decision for the full
history.** There is no stored value and no per-request resolution at all — theme is not data,
it is a pure CSS computation.

```ts
type ThemeName = "light" | "dark"; // still the vocabulary; not backed by any stored value
```

**Rules**:
- Every themed token is a `light-dark()` pair (`styles/themes.css`); the browser picks the
  matching value from the OS's `prefers-color-scheme` before first paint. No cookie, no
  server call, no per-request state.
- An explicit `data-theme="light"` / `data-theme="dark"` attribute on `<html>` — which a
  future theme-toggle feature would set client-side — overrides the OS preference in both
  directions (forces `color-scheme`, which `light-dark()` resolves against). Nothing in this
  slice sets that attribute; no toggle exists yet.

## Navigation destination

A static, code-level list — not fetched, not user-specific. Drives the TabBar/rail/sidebar
chrome and the dev catalog's nav-mapping demo.

```ts
type NavId = "recommend" | "closet" | "outfits" | "profile";

interface NavDestination {
  id: NavId;
  href: string;            // "/recommend" | "/closet" | "/outfits" | "/profile"
  label: string;            // "Recommend" | "Closet" | "Outfits" | "Profile"
  icon: LucideIconName;      // per-tier icon, filled variant used when active
}

// Create is deliberately NOT a NavDestination — it's an overlay launcher (see FR-003).
// Its per-tier presentation (FAB / icon button / labelled pill) is shell-layout config,
// not a nav entry, and it never receives `aria-current`.
```

**Rules**:
- Exactly four entries, identical at every breakpoint (Principle IX) — only their rendered
  form (icon+label / icon-only / icon+label) changes per tier.
- The active entry is derived from the current route (`usePathname()` / server-known
  segment), not stored state.
- The Profile entry's rendered icon swaps to `AvatarInitial` only in the sidebar tier
  (1024px+), per `design-system.md` §5 — this is a render-time rule, not a data difference.

## Component state enums (shared across the library)

Every component in `components/ui/` narrows its own props, but three state shapes recur and
are defined once so components/tests share one vocabulary instead of six ad hoc unions:

```ts
type InteractiveState = "default" | "hover" | "active" | "focus-visible" | "disabled";
type AsyncState = "idle" | "loading" | "error" | "empty"; // only where the design system specifies it
type ThemeableProps = { /* no theme prop — components never branch on theme in JS;
                            theme is entirely a CSS concern via [data-theme] ancestry */ };
```

No component accepts a `theme` prop. This is a deliberate modeling rule, not an omission:
Principle VIII requires every visual value to come from a token, and tokens already flip
value per `[data-theme]` in CSS — a JS-level theme prop would create a second place theme
could be represented and drift from the CSS source of truth.
