# Completion report — Feature 001: App shell, tokens, component library, PWA basics

**From:** implementing agent · **Status:** ready for review · **Branch:** `001-app-shell`
(7 commits on top of `rebuild`, not pushed)

This is the completion report for `docs/handoffs/001-app-shell.md`. Read that file for the
original brief; this one records what actually happened against it.

---

## 1. Workflow followed

`/speckit-specify → /speckit-clarify → /speckit-plan → /speckit-tasks → /speckit-analyze →
/speckit-implement`, all under `specs/001-app-shell/`. `/speckit-analyze` found two real gaps
before implementation started (see §5) and both were fixed in the spec/tasks before coding.

No hook auto-cut the branch (`.specify/extensions.yml` doesn't exist in this repo, contrary to
what the original handoff assumed) — `001-app-shell` was created manually with
`git checkout -b` off `rebuild`.

## 2. What was built

- **Token pipeline** (`frontend/styles/`): system tokens, semantic + light/dark theme blocks,
  the rebuilt type scale from `docs/design-decisions.md` §6 (not §2's superseded sizes).
- **Boot theme**: server-only resolution via a `wtw-theme` cookie (`frontend/lib/theme.ts`),
  read in the root layout before first paint. No client-side `matchMedia` fallback — deliberate,
  see `specs/001-app-shell/research.md`. No theme-toggle UI ships this slice (none is specified
  anywhere in the design docs); the cookie read is what a future toggle needs to work.
- **All 16 shared components** (`frontend/components/ui/`), each with its full state matrix in
  both themes: Button, IconButton, Chip, Badge, Switch, SegmentedControl, TopHeader, TabBar,
  BottomSheet, AvatarInitial, Banner, Input, Textarea, Select, DatePicker, TagInput.
- **Responsive chrome**: bottom bar (0–767px) → 76px rail (768–1023px) → 240px sidebar
  (1024px+), CSS-only, identical four destinations at every tier. Create is an overlay
  launcher composed into TabBar at its per-tier position, never a nav destination.
- **Six stub routes**: `/recommend`, `/closet`, `/outfits`, `/profile`, `/profile/settings`,
  `/add` — chrome + defined empty state only, no data, no auth.
- **Boot/splash state** (`app/loading.tsx`) — `docs/design-decisions.md` §10 assigns this to
  feature 001; it was missing from the first draft of the spec and added after `/speckit-analyze`
  flagged it (see §5).
- **Dev-only component catalog** (`/dev/components`) — renders every state of all 16
  components in both themes side by side; gated out of production (see §6 for a caveat).
- **PWA basics**: `app/manifest.ts`, dual `theme-color` meta tags, safe-area insets on every
  edge-docked element, `/` → `/recommend` redirect.

## 3. Constitution Check

All ten gates recorded honestly in `specs/001-app-shell/plan.md`. Principles I–VII and X are
N/A — this is a frontend-only slice touching no AI/data/taxonomy code. VIII (visual truth) and
IX (one codebase) are the two that apply, and both are satisfied. No Complexity Tracking
entries — no violations.

## 4. Test results

- Vitest: 39/39 passing (component state-matrix unit tests).
- Playwright: 92/92 passing — responsive chrome at all four reference widths, focus-on-navigate,
  focus-visible (keyboard vs. mouse), BottomSheet focus trap/restore, reduced-motion gating,
  PWA manifest contract, server-resolved theme boot, `/` redirect.
- `eslint`, `tsc --noEmit`, `next build` all clean.

Two real bugs were caught and fixed by this testing (not just "tests pass," worth knowing about):
- BottomSheet's responsive CSS block was declared *after* its reduced-motion block, so the
  responsive rule silently re-enabled the transition under reduced motion at tablet/desktop
  widths. Fixed by reordering (reduced-motion now always wins).
- The BottomSheet focus-trap test was too strict about where focus lands on every Tab press;
  Chromium's native `<dialog>` trap transiently parks focus on `<body>` for one tick while
  wrapping from the last focusable element to the first. Adjusted the assertion to the actual
  requirement (focus never reaches a real control *outside* the dialog), not a browser
  implementation detail.

## 5. What `/speckit-analyze` caught before implementation

- **C1**: the boot/splash state (`docs/design-decisions.md` §10 explicitly assigns it to
  feature 001) was absent from the first draft of spec.md/plan.md/tasks.md entirely. Added as
  FR-018 + a task before coding started.
- **C2**: FR-011 requires BottomSheet's open/close motion to be reduced-motion-gated, but no
  task implemented or tested that. Added to the BottomSheet task and its test before coding.

## 6. Open items for you to weigh in on

- **TabBar's four nav icons** (Sparkles/Shirt/LayoutGrid/User for Recommend/Closet/Outfits/
  Profile) have no spec — `design-system.md`'s icon keyword table covers IconButton, not
  TabBar. Visible on every screen. I picked reasonable icons and documented the choice in
  `lib/nav.ts`'s comment, but did not add it to `docs/design-decisions.md` — your call whether
  it warrants formalizing there.
- **Lighthouse's PWA category has been removed** from the currently installed version
  (13.4.1) — `--only-categories=pwa` errors outright. I verified installability manually
  (manifest has every field Chrome's criteria require; all other Lighthouse categories score
  1.0) and recorded this in `quickstart.md` so the next person doesn't hit the same surprise.
  Full `beforeinstallprompt` firing can't be confirmed until feature 007's service worker
  exists.
- **Real-device safe-area check skipped** — no physical device available in this environment.
  Someone with a notched iPhone needs to do the check in `quickstart.md` §6 before this is
  truly done.
- **Playwright's own `webServer` auto-spawn hangs in this sandboxed environment** for reasons
  unrelated to the app (confirmed via minimal repro). Tests currently run against a manually
  started `next dev` server with `reuseExistingServer`; `playwright.config.ts`'s `webServer`
  is still configured for environments (likely CI) where this doesn't reproduce — worth a
  sanity check the first time this runs in CI.

## 7. Not done, deliberately

- **Branch not pushed, no PR opened** — pushing is outside this session's scope per your
  standing instruction. `001-app-shell` (7 commits on top of `rebuild`) is ready whenever
  someone wants to push it and open the PR into `rebuild`.
- Task list: 66/68 tasks checked off in `specs/001-app-shell/tasks.md`. The two open ones are
  the real-device check and opening the PR, both above.
