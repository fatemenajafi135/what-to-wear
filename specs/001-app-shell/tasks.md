# Tasks: App shell, design tokens, component library, and PWA basics

**Input**: Design documents from `/specs/001-app-shell/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md — all present

**Tests**: Included. `plan.md`'s Technical Context already commits to Vitest + React Testing
Library (component state-matrix tests) and Playwright (browser-only behavior: focus-visible,
reduced motion, focus trap, viewport resize) as this feature's testing stack — this is a
foundation slice every later feature builds on, so its state-matrix and a11y guarantees are
worth locking in with tests now.

**Organization**: Tasks are grouped by user story per `spec.md`'s three stories (US1 and US2
are both P1; US3 is P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3
- File paths are exact, relative to the repository root

## Path Conventions

Fixed by the constitution — `frontend/app/`, `frontend/components/`, `frontend/styles/`,
`frontend/lib/`, `frontend/e2e/`. No `ios/`/`android/`/mobile path exists (Principle IX).

---

## Phase 1: Setup

**Purpose**: Project initialization — `frontend/` today holds only `public/` and
`vercel.json`; the Next.js app itself does not exist yet.

- [X] T001 Create the Next.js App Router project skeleton in `frontend/` — `package.json`,
      `tsconfig.json` (strict mode), `next.config.ts` — reusing the existing
      `frontend/public/` and `frontend/vercel.json` unchanged
- [X] T002 [P] Add dependencies to `frontend/package.json`: `next`, `react`, `react-dom`,
      `lucide-react`; dev dependencies: `typescript`, `@types/react`, `@types/node`,
      `eslint`, `eslint-config-next`, `vitest`, `@vitejs/plugin-react`,
      `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`, `@playwright/test`
- [X] T003 [P] Configure Vitest in `frontend/vitest.config.ts` (jsdom environment, React
      plugin, path aliases matching `tsconfig.json`)
- [X] T004 [P] Configure Playwright in `frontend/playwright.config.ts` with projects for the
      four reference viewport widths (320, 768, 1024, 1440) and reduced-motion emulation
- [X] T005 [P] Configure `frontend/eslint.config.mjs` extending `next/core-web-vitals` +
      typescript rules

**Checkpoint**: `npm install && npm run dev` boots an empty Next.js app.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The token pipeline, boot-theme mechanism, and the five nav-critical components
that both P1 user stories depend on. Nothing in Phase 3 or 4 can be verified before this
phase is done.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Create `frontend/styles/tokens.css` with the system tokens from
      `design/design-system.md` §1.1 (motion, z-index, radius, spacing, focus-ring-offset)
      verbatim
- [X] T007 Create `frontend/styles/themes.css` with semantic tokens + light/dark
      `[data-theme]` blocks per `design/design-system.md` §1.2, using the **rebuilt** type
      scale (`--font-size-2xs` … `--font-size-4xl`, two tiers breaking at 1024px) from
      `docs/design-decisions.md` §6 in place of §2's superseded sizes
- [X] T008 Create `frontend/styles/globals.css`: CSS reset, base element styles, the shared
      44px hit-area pseudo-element pattern as a reusable class, and the true
      `:focus-visible` rule (`outline` + `outline-offset`, no bare-`:focus` box-shadow) per
      `docs/design-decisions.md` §4
- [X] T009 [P] Create `frontend/lib/theme.ts`: `ThemeName` type, `THEME_COOKIE` constant
      (`"wtw-theme"`), `resolveTheme()` server helper per `data-model.md` (cookie wins,
      else fixed `"light"` default — no client `matchMedia` fallback)
- [X] T010 [P] Create `frontend/lib/nav.ts`: `NavDestination` type and the fixed four-entry
      nav config (Recommend, Closet, Outfits, Profile) per `data-model.md`
- [X] T011 [P] Create `frontend/lib/fonts.ts`: Instrument Sans via `next/font/google`
      (weights 400/500/600/700) with the documented system fallback stack
- [X] T012 Implement `frontend/app/layout.tsx`: call `resolveTheme()` and set `data-theme` on
      `<html>` directly in the server-rendered markup, inject the font variable, render both
      light/dark `theme-color` meta tags, set the `viewport` export with
      `viewportFit: "cover"`, import `tokens.css`/`themes.css`/`globals.css`, wrap children
      in `role="main"`
- [X] T013 Implement `frontend/app/loading.tsx`: the boot/splash pre-hydration state per
      `docs/design-decisions.md` §10 ("Not a route. It is the app-shell's pre-hydration
      state... Belongs to feature 001") — centered `mark.svg` (32px, from
      `design/assets/mark.svg`) on `--color-background`, "What to Wear" wordmark in the
      Display style (`--font-size-3xl`/`--font-size-4xl` per tier), a pulse animation gated
      by `prefers-reduced-motion` with the static `opacity: 0.7` fallback pattern from
      `design/known-gaps.md` §3. Uses Next.js's `loading.tsx` Suspense-boundary convention —
      the idiomatic place for a pre-hydration/route-loading state in App Router, needing no
      bespoke splash-screen plumbing
- [X] T014 [P] Implement `frontend/components/ui/Button/Button.tsx` +
      `Button.module.css`: primary/secondary/outline variants, full/intrinsic/stretch width
      modes, default/hover/active/focus-visible/disabled/loading/error states per
      `design/design-system.md` §3 and `contracts/component-api.md`
- [X] T015 [P] Implement `frontend/components/ui/IconButton/IconButton.tsx` +
      `IconButton.module.css`: icon-keyword → `lucide-react` map, 44px hit area, per-icon
      `aria-label` defaults, default/hover/active/focus-visible/disabled states
- [X] T016 [P] Implement `frontend/components/ui/AvatarInitial/AvatarInitial.tsx` +
      `AvatarInitial.module.css`: sizes 32–72px, `--color-primary` fill, single initial, no
      interactive states
- [X] T017 Implement `frontend/components/ui/TopHeader/TopHeader.tsx` +
      `TopHeader.module.css` (depends on T014, T015): title renders as `<h1>` with
      `tabIndex={-1}` for focus-on-navigate, optional subtitle, optional back `IconButton`,
      `rightSlot` none/icon/pill variants, both title and subtitle ellipsis-truncate
- [X] T018 Implement `frontend/components/ui/TabBar/TabBar.tsx` + `TabBar.module.css`
      (depends on T015, T016): three CSS-toggled sibling markups (bar <768px, rail
      768–1023px, sidebar 1024px+), active state with `aria-current="page"`, Create action
      presented per tier, Profile swaps to `AvatarInitial` only in the sidebar tier
- [X] T019 Implement `frontend/components/shell/CreateLauncher.tsx`: per-tier overlay
      launcher (FAB / icon button / labelled pill) that opens `/add` and never receives
      `aria-current`
- [X] T020 Implement `frontend/app/(app)/layout.tsx` (depends on T017, T018, T019):
      authenticated shell composing `TabBar` + `CreateLauncher` + main content region, with
      a route-change effect that moves focus to the new screen's `<h1>`
- [X] T021 Implement `frontend/app/page.tsx`: `redirect("/recommend")` (no signed-out branch
      exists yet — see `spec.md` Assumptions)

**Checkpoint**: Foundation ready — both P1 user stories can now proceed.

---

## Phase 3: User Story 1 - Consistent chrome at any device size (Priority: P1) 🎯 MVP

**Goal**: The same four destinations are reachable at every breakpoint through chrome
appropriate to that size, with no broken layout and correct focus-on-navigate behavior.

**Independent Test**: Load each stub route at 320px, 768px, 1024px and 1440px and confirm the
same four destinations are present and reachable, with only the chrome's presentation
changing; navigate between them and confirm focus lands on each new `<h1>`.

### Tests for User Story 1

- [X] T022 [P] [US1] Playwright test asserting correct nav markup (bar/rail/sidebar) and all
      four destinations reachable at 320/768/1024/1440px in
      `frontend/e2e/chrome-breakpoints.spec.ts`
- [X] T023 [P] [US1] Playwright test asserting focus moves to the new screen's `<h1>` on
      every primary navigation in `frontend/e2e/focus-on-navigate.spec.ts`

### Implementation for User Story 1

- [X] T024 [P] [US1] Implement `frontend/app/(app)/recommend/page.tsx`: `TopHeader` title
      "Styling" + chrome-only empty placeholder (no chat state — out of scope)
- [X] T025 [P] [US1] Implement `frontend/app/(app)/closet/page.tsx`: `TopHeader` title
      "Closet" + `closet.empty.first_run` copy and `Button` CTA per
      `design/design-system.md` §6
- [X] T026 [P] [US1] Implement `frontend/app/(app)/outfits/page.tsx`: `TopHeader` title
      "Outfits" + `outfits.empty.first_run` copy and CTA
- [X] T027 [P] [US1] Implement `frontend/app/(app)/profile/page.tsx`: visually-hidden
      `<h1>Profile</h1>`, empty profile-card stub layout
- [X] T028 [US1] Implement `frontend/app/(app)/profile/settings/page.tsx` (depends on T027):
      `TopHeader` title "Settings", back arrow to `/profile`, chrome-only section-switcher
      stub (no live fields wired this slice)
- [X] T029 [US1] Implement `frontend/app/(app)/add/page.tsx`: overlay-launcher stub screen;
      closing with no navigation history falls back to `/closet` per
      `docs/design-decisions.md` §9
- [X] T030 [US1] Verify the 320/768/1024/1440 responsive breakpoints hold across
      `frontend/styles/themes.css` and the Foundational chrome components; fix any layout
      break found

**Checkpoint**: User Story 1 is fully functional and independently testable.

---

## Phase 4: User Story 2 - Every shared component reads correctly in light and dark, in every state (Priority: P1)

**Goal**: All sixteen shared components (five already built in Foundational, eleven more
here) implement their full documented state matrix in both themes, mechanically verifiable
via the dev-only catalog route.

**Independent Test**: Render all sixteen components in `/dev/components`, cycle every
documented state in both themes, confirm no raw color/pixel value appears outside the token
files.

### Tests for User Story 2

- [X] T031 [P] [US2] Vitest state-matrix test in `frontend/components/ui/Chip/Chip.test.tsx`
- [X] T032 [P] [US2] Vitest state-matrix test in
      `frontend/components/ui/Badge/Badge.test.tsx`
- [X] T033 [P] [US2] Vitest test asserting `role="switch"`, `aria-checked`, keyboard
      Space/Enter toggle in `frontend/components/ui/Switch/Switch.test.tsx`
- [X] T034 [P] [US2] Vitest state-matrix test in
      `frontend/components/ui/SegmentedControl/SegmentedControl.test.tsx`
- [X] T035 [P] [US2] Vitest test asserting `role="status" aria-live="polite"` and all three
      variants in `frontend/components/ui/Banner/Banner.test.tsx`
- [X] T036 [P] [US2] Vitest test asserting label/error/`aria-invalid`/password-toggle
      behavior in `frontend/components/ui/Input/Input.test.tsx`
- [X] T037 [P] [US2] Vitest state-matrix test in
      `frontend/components/ui/Textarea/Textarea.test.tsx`
- [X] T038 [P] [US2] Vitest state-matrix test in
      `frontend/components/ui/Select/Select.test.tsx`
- [X] T039 [P] [US2] Vitest test asserting `toLocaleDateString` display formatting in
      `frontend/components/ui/DatePicker/DatePicker.test.tsx`
- [X] T040 [P] [US2] Vitest test asserting `role="list"`/`role="listitem"`, Enter-to-commit,
      Backspace-to-remove, and the live region in
      `frontend/components/ui/TagInput/TagInput.test.tsx`
- [X] T041 [P] [US2] Playwright test for `BottomSheet` focus trap, focus restore on close,
      and Escape-to-close in `frontend/e2e/bottom-sheet-focus-trap.spec.ts`
- [X] T042 [P] [US2] Playwright test asserting the focus ring shows on keyboard Tab and is
      absent on mouse click, across Button/IconButton/Chip/Switch/Input, in
      `frontend/e2e/focus-visible.spec.ts`
- [X] T043 [P] [US2] Playwright test asserting `prefers-reduced-motion: reduce` disables the
      skeleton pulse, Switch thumb-slide, boot logo pulse (T013's `loading.tsx`), and
      BottomSheet's open/close backdrop-fade/panel-translate transition (replaced by an
      instant show/hide) in `frontend/e2e/reduced-motion.spec.ts`

### Implementation for User Story 2

- [X] T044 [P] [US2] Implement `frontend/components/ui/Chip/Chip.tsx` + `Chip.module.css`:
      active/inactive/disabled, 44px hit area
- [X] T045 [P] [US2] Implement `frontend/components/ui/Badge/Badge.tsx` + `Badge.module.css`:
      citation/status/muted/count tones, non-interactive
- [X] T046 [P] [US2] Implement `frontend/components/ui/Switch/Switch.tsx` +
      `Switch.module.css`: `role="switch"`, `aria-checked`, `aria-disabled`, `tabIndex`,
      Space/Enter keydown handler, reduced-motion-gated thumb-slide
- [X] T047 [P] [US2] Implement
      `frontend/components/ui/SegmentedControl/SegmentedControl.tsx` +
      `SegmentedControl.module.css`: 2–3 options, active/inactive, control-level disabled
- [X] T048 [P] [US2] Implement `frontend/components/ui/Banner/Banner.tsx` +
      `Banner.module.css`: offline/error/info variants, `role="status" aria-live="polite"`,
      error variant's 3px inline-start border per `docs/design-decisions.md` §10
- [X] T049 [US2] Implement `frontend/components/ui/BottomSheet/BottomSheet.tsx` +
      `BottomSheet.module.css` (depends on T008 for the hit-area/focus utilities): native
      `<dialog>` + `showModal()`, `aria-labelledby`, normal/loading/error/empty states,
      danger row tone, bottom-anchored <768px / centered dialog ≥768px, safe-area-aware
      bottom padding, plus the backdrop-fade + panel-translate open/close motion from
      `design/design-system.md`'s "BottomSheet & toast motion" section (`--motion-duration-base`
      decelerate on open, `--motion-duration-fast` accelerate on close), gated by
      `prefers-reduced-motion` (instant show/hide fallback, no transition) — this is FR-011's
      BottomSheet clause
- [X] T050 [P] [US2] Implement `frontend/components/ui/Input/Input.tsx` +
      `Input.module.css`: 44px height, 16px font (iOS zoom guard), hover/focus-visible/
      error/disabled/read-only states, password show/hide `IconButton` per
      `docs/design-decisions.md` §1.2
- [X] T051 [P] [US2] Implement `frontend/components/ui/Textarea/Textarea.tsx` +
      `Textarea.module.css`: `min-height: 94px`, `resize: vertical`, shares Input's state
      treatment
- [X] T052 [P] [US2] Implement `frontend/components/ui/Select/Select.tsx` +
      `Select.module.css`: native `<select>` styled to match Input, chevron-down background
      image, `appearance: none`
- [X] T053 [P] [US2] Implement `frontend/components/ui/DatePicker/DatePicker.tsx` +
      `DatePicker.module.css`: native `input[type=date]` styled as Input,
      `toLocaleDateString` display formatting
- [X] T054 [US2] Implement `frontend/components/ui/TagInput/TagInput.tsx` +
      `TagInput.module.css` (depends on T044): Input-shaped growing container, committed
      values rendered as active `Chip`s with a trailing `×` remove button, Enter-to-commit /
      Backspace-to-remove, `role="list"`/`role="listitem"`, visually-hidden live region
- [X] T055 [US2] Implement `frontend/app/dev/components/page.tsx` (depends on all sixteen
      components existing): catalog rendering every state of all sixteen components in both
      themes side by side; calls `notFound()` when `process.env.NODE_ENV === "production"`

**Checkpoint**: All sixteen components are verified in both themes; US1 + US2 together
deliver a fully chromed, fully componentized shell.

---

## Phase 5: User Story 3 - The app installs cleanly and boots without a visual glitch (Priority: P2)

**Goal**: Correct manifest, dual meta tags, safe-area insets, `/` redirect, no theme flash,
Lighthouse-installable.

**Independent Test**: Lighthouse PWA audit passes against a production build; forced
light/dark cold reloads never show the wrong theme; a real notched device clears safe-area
insets in installed standalone mode.

### Tests for User Story 3

- [X] T056 [P] [US3] Playwright test asserting `manifest.webmanifest` matches
      `contracts/manifest.md` exactly (including `/add`/`/recommend` shortcut URLs) in
      `frontend/e2e/manifest.spec.ts`
- [X] T057 [P] [US3] Playwright test in `frontend/e2e/theme-boot.spec.ts` asserting (a) a
      `wtw-theme=dark` cookie produces `data-theme="dark"` in the raw server-rendered HTML
      response body (checked before any script runs, not just the final DOM) regardless of
      OS `prefers-color-scheme`, and (b) with no cookie set and OS forced to dark, the served
      HTML still carries the fixed `data-theme="light"` default with no later client-side
      flip to dark — this is the mechanism SC-005's "0 flashes across 20 reloads" actually
      depends on, so covering both branches once is the automated equivalent of the manual
      repeat-reload pass in `quickstart.md` §5
- [X] T058 [P] [US3] Playwright test asserting `/` redirects to `/recommend` in
      `frontend/e2e/root-redirect.spec.ts`

### Implementation for User Story 3

- [X] T059 [US3] Implement `frontend/app/manifest.ts` per `contracts/manifest.md` (name,
      icons, shortcuts pointing at `/add` and `/recommend`, `start_url: "/?source=pwa"`)
- [X] T060 [US3] Cross-check `frontend/app/layout.tsx` (T012) against `contracts/manifest.md`
      for the dual `theme-color` meta tags and `viewport-fit=cover`; add anything missing
- [X] T061 [US3] Apply safe-area inset CSS to every edge-docked element: `TabBar` bottom
      padding `env(safe-area-inset-bottom, 22px)` in
      `frontend/components/ui/TabBar/TabBar.module.css`; `BottomSheet` bottom padding
      `calc(30px + env(safe-area-inset-bottom))` in
      `frontend/components/ui/BottomSheet/BottomSheet.module.css`; sticky `TopHeader`
      `env(safe-area-inset-top)` with no floor
- [ ] T062 [US3] Run a Lighthouse PWA-installability audit against a production build
      (`npm run build && npm start`) and fix any reported gap
- [ ] T063 [US3] Perform the manual real-device safe-area check from `quickstart.md` §6 on a
      notched iPhone in installed standalone mode; record the result

**Checkpoint**: All three user stories are independently functional; PWA basics verified.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T064 [P] Run `npm run lint`, `npx tsc --noEmit`, and `npm run build` in `frontend/`;
      fix all errors (constitution CI gates)
- [X] T065 [P] Grep `frontend/components/` and `frontend/app/` CSS for raw hex codes or
      magic pixel literals outside `styles/tokens.css`/`styles/themes.css`; fix any found
      (Principle VIII gate)
- [ ] T066 Run the full `quickstart.md` validation checklist end-to-end and record results
- [X] T067 Grep the new `frontend/` tree for anything ported from
      `design/prototype/_scaffolding/` (`ios-frame`, `support.js`, `devOverride`,
      `--wtw-proto-inset-top`, floating theme toggle) and remove any match found
- [ ] T068 Open the PR from `001-app-shell` into `rebuild` per
      `docs/handoffs/001-app-shell.md`'s workflow

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS both US1 and US2
- **US1 (Phase 3)** and **US2 (Phase 4)**: Both depend only on Foundational; independent of
  each other (US1 uses the five Foundational components; US2 builds the remaining eleven)
- **US3 (Phase 5)**: Depends on Foundational (theme cookie, layout) and on US1's routes
  existing to redirect into (`/recommend`); independent of US2
- **Polish (Phase 6)**: Depends on all three user stories being complete

### Within Each User Story

- Tests before implementation (write first, confirm they fail)
- Foundational/shared components before screens that consume them
- Story complete before moving to Polish

### Parallel Opportunities

- All Setup tasks marked [P] run in parallel
- T014–T016 (Button, IconButton, AvatarInitial) run in parallel within Foundational
- US1 and US2 can be staffed in parallel once Foundational is done
- All [P] tests within a story run in parallel
- Most component implementations within US2 (T044–T048, T050–T053) run in parallel — only
  T049 (needs T008) and T054 (needs T044) have an in-story dependency

---

## Parallel Example: Foundational components

```bash
Task: "Implement frontend/components/ui/Button/Button.tsx + Button.module.css"
Task: "Implement frontend/components/ui/IconButton/IconButton.tsx + IconButton.module.css"
Task: "Implement frontend/components/ui/AvatarInitial/AvatarInitial.tsx + AvatarInitial.module.css"
```

## Parallel Example: User Story 2 components

```bash
Task: "Implement frontend/components/ui/Chip/Chip.tsx + Chip.module.css"
Task: "Implement frontend/components/ui/Badge/Badge.tsx + Badge.module.css"
Task: "Implement frontend/components/ui/Switch/Switch.tsx + Switch.module.css"
Task: "Implement frontend/components/ui/SegmentedControl/SegmentedControl.tsx + SegmentedControl.module.css"
Task: "Implement frontend/components/ui/Banner/Banner.tsx + Banner.module.css"
Task: "Implement frontend/components/ui/Input/Input.tsx + Input.module.css"
Task: "Implement frontend/components/ui/Textarea/Textarea.tsx + Textarea.module.css"
Task: "Implement frontend/components/ui/Select/Select.tsx + Select.module.css"
Task: "Implement frontend/components/ui/DatePicker/DatePicker.tsx + DatePicker.module.css"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup
2. Phase 2: Foundational (blocks everything)
3. Phase 3: User Story 1
4. **STOP and VALIDATE**: run T022/T023, confirm chrome holds at all four widths
5. Demo the chrome + stub routes

### Incremental Delivery

1. Setup + Foundational → chrome-critical components + token pipeline ready
2. Add US1 → validate independently → demo (MVP)
3. Add US2 → validate via `/dev/components` → demo full component library
4. Add US3 → validate Lighthouse + theme-boot + safe-area → demo installable PWA
5. Polish → lint/build/quickstart clean → open PR

---

## Notes

- [P] tasks touch different files with no unmet dependency
- Both US1 and US2 are P1 — they were split because they are independently testable and
  deliverable, not because one outranks the other; a team of two could take one each right
  after Foundational
- Commit after each task or logical group, per the repository's normal commit conventions
  (`feat(001): ...`)
- Avoid: vague tasks, two tasks writing the same file in parallel, cross-story dependencies
  that break independent testability
