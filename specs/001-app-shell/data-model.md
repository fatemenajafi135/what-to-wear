# Data Model: App shell, design tokens, component library, and PWA basics

This slice persists nothing to a database and calls no API — there is no domain data model.
The two "entities" from the spec's Key Entities section are configuration/UI-state shapes,
recorded here as the TypeScript types other tasks and future features will import.

## Theme preference

Not stored server-side, not associated with a user record (no auth exists yet). Represented
purely as a cookie value plus a resolved value used for rendering.

```ts
type ThemeName = "light" | "dark";

const THEME_COOKIE = "wtw-theme"; // values: ThemeName only

interface ResolvedTheme {
  theme: ThemeName;       // what actually renders this request
  source: "cookie" | "default"; // where it came from — no client matchMedia fallback (see research.md)
}
```

**Rules**:
- If the `wtw-theme` cookie is present and is exactly `"light"` or `"dark"`, it wins.
- Otherwise `theme` resolves to the fixed default `"light"` (matches the manifest's
  `background_color` approximation).
- No lifecycle/transition beyond "set" — nothing in this slice writes the cookie; the read
  path exists for a future theme-toggle feature to use (see `research.md`).

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
