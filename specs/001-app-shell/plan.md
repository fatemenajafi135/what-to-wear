# Implementation Plan: App shell, design tokens, component library, and PWA basics

**Branch**: `001-app-shell` | **Date**: 2026-07-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-app-shell/spec.md`

## Summary

Stand up the Next.js App Router application shell for What to Wear: a three-layer CSS
design-token pipeline (system → semantic → light/dark theme blocks) with server-resolved,
flash-free boot theming; a sixteen-component shared UI library (the eleven design-system
components plus the five form controls from `docs/design-decisions.md` §1), each shipping its
full documented state matrix in both themes; CSS-only responsive chrome (bottom tab bar →
76px icon rail → 240px sidebar) wrapping six stub routes that render only their chrome and
empty state; a dev-only component-catalog route for mechanically verifying every state; and
PWA basics (`app/manifest.ts`, dual `theme-color` meta tags, safe-area insets, `/` redirect).
No auth, no real data, no service worker — those belong to features 002 and 007.

## Technical Context

**Language/Version**: TypeScript 5.x on Node.js 20 LTS (Next.js current LTS requirement)

**Primary Dependencies**: Next.js (App Router) + React, `lucide-react` (icon set named
explicitly by the design system), `next/font/google` for Instrument Sans — no CSS framework,
no CSS-in-JS runtime, no component library beyond what this feature builds

**Storage**: N/A. Boot theme is not stored or read per-request at all — it resolves entirely
in CSS via `light-dark()` against `prefers-color-scheme`, so the stub routes stay statically
rendered. (Originally specified as a first-party cookie read via `cookies()`; corrected by
`docs/handoffs/001-app-shell-fix-theme.md` — see `research.md`'s amended "Boot-time theme"
decision.)

**Testing**: Vitest + React Testing Library for component state-matrix unit tests; Playwright
for browser-only behavior (real `:focus-visible`, `prefers-reduced-motion` emulation, viewport
resize across the four reference widths, focus trap/restore) — see `research.md` for the
comparison against alternatives

**Target Platform**: Evergreen desktop and mobile browsers (Chrome, Safari, Firefox, Edge),
plus the same app installed as a standalone PWA on Android/iOS — one build serves both

**Project Type**: Web application (Next.js App Router), single frontend package per the
constitution's fixed layout — no mobile-app option exists or is created

**Performance Goals**: No visible flash of the wrong theme on any cold start (0 of 20 forced
light/dark reloads, per SC-005); CSS-only breakpoint switching with no layout thrash on resize

**Constraints**: No raw hex or magic pixel value in component code — every value reads a
token (Principle VIII); 44×44px minimum hit targets; WCAG 2.1 AA; identical routes at every
form factor with only chrome changing (Principle IX); no service worker, caching, or install
prompt in this slice

**Scale/Scope**: 6 stub routes + 1 dev-only catalog route, 16 shared components each with a
2–7-state matrix in 2 themes, 3 responsive tiers

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** N/A. This slice touches no retrieval,
      chunking, ingest, knowledge base, scoring, pipeline, or eval code — it is frontend
      chrome and tokens only. Nothing is regenerated or refactored.
- [x] **II — Deterministic scoring.** N/A. No outfit scoring exists in this slice; the Match
      score UI (§ Scores) belongs to the Outfits/Recommend features, not this one.
- [x] **III — Style gates wardrobe.** N/A. No retrieval of any kind happens in this slice.
- [x] **IV — Grounded output.** N/A. No items, citations, or rationale are rendered — every
      route is an empty-state stub with no data.
- [x] **V — Scorers are eval metrics.** N/A. No quality judgement exists in this slice.
- [x] **VI — Schema stability.** N/A. No item taxonomy is touched — stub routes render no
      item data at all.
- [x] **VII — Contracts.** N/A this slice — no API call exists yet, so there is no OpenAPI
      contract to consume. Recorded here so feature 002+ cannot silently skip it: the first
      feature that fetches real data MUST consume OpenAPI-generated types, not hand-write them.
- [x] **VIII — Visual truth.** Applies, and is this slice's central gate. Every token comes
      from `design/design-system.md` §1 as superseded by `docs/design-decisions.md` §6 (type
      scale) and §4/§5 (focus ring, disabled convention); no code is copied from
      `design/prototype/`, and nothing from `design/prototype/_scaffolding/` is ported (see
      Traps in the handoff). All 16 components implement their full state matrix, verified via
      the dev-only catalog route (FR-005a). **Partial by explicit scope, not by omission**: the
      six *route* stubs render chrome + empty state only, per the handoff's own scope line
      ("every route you create is a stub that renders its chrome and its empty state") — a
      route-level loading/error/offline state has nothing real to load, error on, or lose
      connectivity to until a feature with actual data fetching exists (002+). The *component
      library* itself still ships loading/error/empty states wherever the design system
      specifies them per-component (Button, BottomSheet, Banner), so Principle VIII is not
      weakened — it is satisfied at the layer where this slice actually operates. WCAG AA
      (44px targets, `:focus-visible`, one `<h1>` per screen with focus-on-navigate, focus
      trap/restore in BottomSheet, reduced motion) is in scope and required.
- [x] **IX — One codebase.** Applies and is fully in scope: one Next.js app, identical routes
      at 0–767 / 768–1023 / 1024+, CSS-only chrome switching, no `ios/`/`android/` directory,
      no user-agent branching on reachability. Of the four display-mode × form-factor
      combinations, the three that don't depend on an install prompt (out of scope until 007)
      are fully buildable and testable now: safe-area insets resolve for real in standalone
      mode and are inert in browser-tab mode, at both mobile and desktop widths.
- [x] **X — Documents are data.** N/A. No document or corpus is introduced.

**Gates requiring justification in Complexity Tracking: none.** The only "Partial" reading
(VIII, route-level loading/error/offline) is an explicit, handoff-authorized scope boundary
for this slice, not a violation — it is called out above for transparency rather than filed
as a tracked exception.

## Project Structure

### Documentation (this feature)

```text
specs/001-app-shell/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   ├── component-api.md
│   └── manifest.md
├── checklists/
│   └── requirements.md
└── tasks.md              # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
frontend/
├── app/
│   ├── layout.tsx                 # root layout: no per-request work (static) — theme
│   │                               # resolves in CSS; Instrument Sans via next/font, dual
│   │                               # theme-color metas
│   ├── page.tsx                   # "/" → redirect("/recommend") (no real auth this slice)
│   ├── loading.tsx                 # boot/splash pre-hydration state (design-decisions.md §10)
│   ├── manifest.ts                # PWA manifest (known-gaps.md §-2 JSON, shortcuts per
│   │                               # design-decisions.md §9)
│   ├── (app)/
│   │   ├── layout.tsx             # authenticated chrome: TabBar/rail/sidebar + Create launcher
│   │   ├── recommend/page.tsx
│   │   ├── closet/page.tsx
│   │   ├── outfits/page.tsx
│   │   ├── profile/
│   │   │   ├── page.tsx           # visually-hidden <h1>Profile</h1> per design-system §8
│   │   │   └── settings/page.tsx
│   │   └── add/page.tsx           # overlay-launcher stub; not a TabBar destination
│   └── dev/
│       └── components/page.tsx    # catalog route; notFound() when NODE_ENV=production
├── components/
│   ├── ui/                        # one dir per shared component, colocated test + styles
│   │   ├── Button/  IconButton/  Chip/  Badge/  Switch/  SegmentedControl/
│   │   ├── TopHeader/  TabBar/  BottomSheet/  AvatarInitial/  Banner/
│   │   └── Input/  Textarea/  Select/  DatePicker/  TagInput/
│   └── shell/                     # NavBar (bar/rail/sidebar), CreateLauncher, SkipLink
├── styles/
│   ├── tokens.css                 # §1.1 system tokens (theme-independent)
│   ├── themes.css                 # §1.2 semantic tokens + light/dark [data-theme] blocks
│   └── globals.css                # reset, base element styles, font fallback stack
├── lib/                            # (no theme.ts — removed, see fix-theme handoff: theme
│                                   # resolution is pure CSS with nothing to compute in JS)
├── e2e/                           # Playwright: breakpoints, keyboard pass, focus, motion
└── public/                        # icons/ + logo.svg already exist; untouched

backend/    # untouched by this feature
infra/      # untouched by this feature
```

**Structure Decision**: This feature only adds files under `frontend/`. It does not touch
`backend/` or `infra/` at all — there is no API, no database, and no corpus in this slice.
The `frontend/` tree above is new in its entirety except `public/`, which already holds the
verified icon set and must not be regenerated.

## Complexity Tracking

*No violations — table intentionally left empty.*
