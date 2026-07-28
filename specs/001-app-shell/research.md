# Research: App shell, design tokens, component library, and PWA basics

Phase 0 output. Every Technical Context item below was already decidable from the
constitution, the handoff, and the design docs — none required external investigation, so
these are recorded as decisions with rationale rather than open research tasks.

## Styling approach: CSS Modules + plain CSS custom properties

**Decision**: One `.module.css` per component, reading tokens declared as CSS custom
properties in `styles/tokens.css` (system) and `styles/themes.css` (semantic + light/dark
blocks). No Tailwind, no CSS-in-JS runtime.

**Rationale**: `design/design-system.md` §1 already expresses every token as a literal CSS
custom property block — adopting that verbatim is the zero-translation path. CSS Modules
ships with Next.js at zero extra config or dependency, scopes class names automatically, and
keeps "every value reads a token" (Principle VIII) mechanically checkable: a reviewer or a
lint rule can grep component CSS for hex codes or bare pixel literals with no framework
indirection to unwrap first.

**Alternatives considered**: Tailwind would require re-deriving every token as a Tailwind
config value — an extra layer of naming the design system doesn't ask for, and a second place
a token could drift from `design-system.md`. CSS-in-JS (styled-components, Emotion) adds a
runtime cost and a dependency for a problem CSS Modules already solves; it also fights the
constitution's "simplicity over abstraction" bar, since there is exactly one concrete styling
need here (scoped, token-driven CSS), not two implementations to abstract over.

## Testing stack: Vitest + React Testing Library, plus Playwright

**Decision**: Vitest + React Testing Library for component state-matrix unit tests
(rendering each state, asserting ARIA attributes/roles, disabled/opacity conventions).
Playwright for behavior that requires a real browser engine: `:focus-visible` vs `:focus`,
`prefers-reduced-motion` emulation, `prefers-color-scheme` + cookie-override interaction,
viewport resize across 320/768/1024/1440px, and BottomSheet focus trap/restore.

**Rationale**: Vitest is ESM-native and starts fast, which matters once 16 components ×
several states each accumulate test files; React Testing Library's role/label-based queries
structurally push toward the accessible markup Principle VIII already requires (a test that
can only find a button by `getByRole('button', { name: ... })` is also proof the accessible
name exists). jsdom (Vitest's default DOM) does not implement `:focus-visible` heuristics,
real media-query matching, or native `<dialog>` focus trapping correctly, so anything
depending on those needs a real engine — Playwright.

**Alternatives considered**: Jest works but is slower to start and needs more ESM/Next.js
config glue than Vitest for no behavioral gain here. Cypress overlaps with Playwright's E2E
role but has a weaker multi-browser/CI story for this project's needs (no Cypress-specific
requirement exists anywhere in the constitution or handoff).

## Boot-time theme: server-read cookie, no client script

**Decision**: A single cookie (`wtw-theme`, values `light` | `dark`) is read in the root
`layout.tsx` via `next/headers`'s `cookies()`. If present, it wins outright. If absent, the
server falls back to a fixed default (`light`, matching the manifest's `background_color`
approximation in `known-gaps.md` §-2) — **not** to a client `matchMedia` read, since that
would require exactly the blocking inline script this decision is meant to avoid. `data-theme`
is set directly in the server-rendered `<html>` tag.

**Consequence, called out explicitly**: without a client-side `prefers-color-scheme` read,
a person whose system is in dark mode but who has never set the cookie will see the light
default on first visit, then get corrected once a mechanism sets the cookie. **No such
mechanism ships in this slice** — no theme-toggle component appears anywhere in the sixteen
required components or the Settings section list in `design-system.md` §4. Building one
would be inventing a screen element the design system never specifies (a Principle VIII
violation in the other direction — adding UI, not skipping it). This is recorded as a real,
named gap for whichever future feature adds a theme control (most naturally Settings), not
silently absorbed. The cookie-read/fallback plumbing this slice builds is exactly what that
future toggle needs to become effective — it only has to set one cookie.

**Rationale for still building the read path now**: `docs/handoffs/001-app-shell.md` §4.1
requires boot theme selection to be closed as a gap in *this* slice ("read `prefers-color-scheme`
before first paint, falling back to a persisted user override"). Interpreting "falling back"
literally would put the override second — but an override that is never reachable in this
slice can't be tested, and a client-side `matchMedia` read reintroduces the exact flash this
requirement exists to prevent, since the server would ship one theme and a script would
possibly swap it after hydration. The cookie-first, server-rendered approach is the only
reading that satisfies "no flash" as an absolute (not "usually no flash"), which is why
`/speckit-clarify` confirmed this ordering explicitly.

**Alternatives considered**: Inline blocking `<script>` in `<head>` reading `localStorage` +
`matchMedia` — works with zero server involvement, but does not resolve `prefers-color-scheme`
on the server, so it cannot help SSR'd content match on the very first response byte, only
before paint on the client; also reintroduces a hand-written script the cookie approach makes
unnecessary. `next-themes` (or similar) library — pulls in a dependency for logic small enough
to hand-write in `lib/theme.ts`, and most such libraries default to the client-script pattern
this decision explicitly rejects.

## Overlay dialog semantics: native `<dialog>`

**Decision**: `BottomSheet` renders a native `<dialog>` element, opened via `showModal()`.

**Rationale**: Native `<dialog>` provides modal focus trapping, `Escape`-to-close, top-layer
stacking, and automatic focus restoration to the invoking element on close — exactly the gap
`docs/handoffs/001-app-shell.md` Trap 6 and `design-system.md` §3 flag as missing from the
prototype. Using the platform feature means zero bespoke focus-trap code to write, test, or
get wrong across the sheet's several call sites (item menu, outfit menu, filter sheet), which
is what the constitution's "introduce an abstraction only when there's a measured problem"
bar asks for — the problem here is genuinely solved already, one level down.

**Alternatives considered**: A hand-rolled focus-trap hook (`Tab`/`Shift+Tab` cycling,
manual `aria-modal`, manual focus restore) duplicates what `<dialog>` gives for free and is
one more place a11y bugs hide. A third-party focus-trap library is an extra dependency for a
solved platform problem.

## PWA manifest: `app/manifest.ts`

**Decision**: Use Next.js's typed `MetadataRoute.Manifest` file convention
(`app/manifest.ts`), returning the exact object from `known-gaps.md` §-2 with `shortcuts[].url`
changed to `/add` and `/recommend` per `docs/design-decisions.md` §9, and `start_url` left at
`/?source=pwa` per that same decision.

**Rationale**: `app/manifest.ts` is generated at build time, is type-checked, and needs no
manual `<link rel="manifest">` — Next.js injects it. This keeps the manifest as code (checked
by `tsc`) rather than a hand-maintained static JSON file that can silently drift from the
route table.

**Alternatives considered**: A static `public/manifest.json` — works, but is untyped and is
exactly the kind of hand-maintained artifact the OpenAPI-contracts principle (VII) warns
against in spirit, even though this particular file has no backend counterpart to drift from.

## Font loading: `next/font/google`

**Decision**: Load Instrument Sans (400/500/600/700) via `next/font/google`, with the
documented system fallback stack (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
sans-serif`) as the `next/font` fallback list.

**Rationale**: `next/font` self-hosts the font at build time (no runtime request to Google
Fonts, better privacy and no render-blocking network dependency) and exposes the resolved
family name as a CSS variable, which composes cleanly with the token pipeline. This is the
Next.js-idiomatic replacement for the `<link>`-based loading `design-system.md` describes,
without changing the visible font stack.

## Icon library: `lucide-react`

**Decision**: The `lucide-react` npm package, imported per-icon (tree-shakeable), using the
exact icon names `design-system.md` §3 maps per keyword (`arrow-left`, `x`, `settings`,
`ellipsis`, `heart`, `sliders-horizontal`, `calendar`, `history`, `plus`, `thumbs-up`).

**Rationale**: The design system names `lucide-react` explicitly as one of the two acceptable
sources ("Lucide (`lucide-react` or the static SVG set)"); the npm package is preferred over
vendoring static SVGs because it ships stroke-width/size props matching the documented 2–2.2px
weight without hand-maintaining a duplicate icon set.

## Boot/splash pre-hydration state: `app/loading.tsx`

**Decision**: Implement the boot/splash state described in `docs/design-decisions.md` §10
(centered `mark.svg` at 32px, Display-style wordmark, reduced-motion-gated pulse) as
`frontend/app/loading.tsx`.

**Rationale**: `docs/design-decisions.md` §10 explicitly assigns this state to feature 001
while also stating it "is not a route" — it is "the app-shell's pre-hydration state." Next.js
App Router's `loading.tsx` file convention is exactly that: an automatic Suspense boundary
fallback shown while a route segment is loading, with zero custom routing or state
management required. It composes with the same tokens and reduced-motion gating pattern
(`design/known-gaps.md` §3) already used by the skeleton pulse.

**Alternatives considered**: A component manually mounted during a client-side "booting"
phase (e.g. gated on a `useEffect` + state flag) would duplicate what `loading.tsx` gives for
free and risks a hydration mismatch; a real splash *route* was rejected outright since the
decision explicitly says this is not a route.

## Dev-only catalog route gating

**Decision**: `app/dev/components/page.tsx` calls Next.js's `notFound()` when
`process.env.NODE_ENV === 'production'`, and is never linked from any nav chrome.

**Rationale**: Satisfies the `/speckit-clarify` decision to build a catalog route while
keeping it "excluded from the production build's discoverable surface" without a second build
target or a separate app — one Next.js codebase throughout, consistent with Principle IX.
