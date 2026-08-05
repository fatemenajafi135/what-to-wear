# Tasks: Offline, caching and the update prompt

**Input**: Design documents from `/specs/014-offline-and-updates/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/route-caching.md, quickstart.md

**Tests**: Included — this feature's Definition of Done (handoff §7) is verification-heavy by
nature (a service worker is only observable at runtime), so both unit tests (for the pieces that
don't need a real SW) and a new production-build Playwright suite (for the pieces that do,
`research.md` R9) are in scope, not optional here.

**Organization**: Tasks are grouped by user story (spec.md priorities). The full five-class route
table (`contracts/route-caching.md`) is genuinely shared infrastructure — every story depends on at
least one class of it — so it lives in Foundational as one cohesive `runtimeCaching` array rather
than being artificially split across stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (offline cold start), US2 (sign-out purge), US3 (expired photo), US4 (update prompt)

## Path Conventions

Frontend-only feature. All paths are under `frontend/`, plus two durable docs already updated in
`/speckit-plan` (`docs/design-decisions.md` §52–53) and one still to update
(`docs/ios-verification-backlog.md`, Polish phase). No backend, no `infra/` changes.

---

## Phase 1: Setup

**Purpose**: Get Serwist into the build before writing any route logic.

- [X] T001 Add `serwist` and `@serwist/next` (9.5.12) to `frontend/package.json` dependencies, `npm install`
- [X] T002 [P] Create `frontend/lib/serviceWorker/cacheNames.ts` — `API_DATA_CACHE = "wtw-api-data"`, `PHOTOS_CACHE = "wtw-photos"`, `USER_SCOPED_CACHE_NAMES` (data-model.md)
- [X] T003 Wrap `frontend/next.config.ts` in `withSerwistInit` (`@serwist/next`) — `swSrc: "app/sw.ts"`, `swDest: "public/sw.js"`, `disable: process.env.NODE_ENV === "development"`

**Checkpoint**: `npm run build` produces `public/sw.js` (still trivial/empty at this point).

---

## Phase 2: Foundational (blocks all user stories)

**Purpose**: The service worker itself, its full route table (`contracts/route-caching.md`), and
the harness needed to prove any of it works in a real browser.

**⚠️ CRITICAL**: No user story task should start until this phase's checkpoint is reached.

- [X] T004 Create `frontend/app/sw.ts` — `Serwist` instance wired to `self.__SW_MANIFEST`, `skipWaiting: false`, `clientsClaim: true`, `runtimeCaching` = `defaultCache` (class 1, from `@serwist/next/worker`) with the explicit class-3 `NetworkOnly` rule (all non-`GET` to the API origin, including `POST /recommend/messages`) and class-2 `NetworkFirst` rule (`GET` to the API origin, `wtw-api-data`, 4s timeout, `ExpirationPlugin({maxEntries:200, maxAgeSeconds:86400})`) and class-4 `CacheFirst` rule (Supabase Storage sign URLs, `wtw-photos`, `ExpirationPlugin({maxEntries:300, maxAgeSeconds:3600})`) all **prepended before** `defaultCache` per `contracts/route-caching.md`
- [X] T005 [P] Create `frontend/components/shell/ServiceWorkerRegistration.tsx` — client component, registers `app/sw.ts` (via `public/sw.js`) on mount, no UI
- [X] T006 Mount `<ServiceWorkerRegistration />` once in `frontend/app/layout.tsx` (root layout, so it covers both the `(auth)` and `(app)` shells)
- [X] T007 [P] Create `frontend/playwright.pwa.config.ts` — separate Playwright config, `webServer` runs `npm run build && npm run start -- -p 3100` (port 3100, not a fresh one: CORS only whitelists 3000/3100 and a third port is a backend change), `testDir: "./e2e-pwa"`, own `npm run e2e:pwa` script in `package.json`
- [X] T008 [P] `frontend/lib/serviceWorker/cacheNames.test.ts` — unit test: `USER_SCOPED_CACHE_NAMES` equals exactly `[API_DATA_CACHE, PHOTOS_CACHE]` (`contracts/route-caching.md` invariant 2)
- [X] T009 `frontend/e2e-pwa/service-worker-smoke.spec.ts` — build+start, load once, assert a service worker reaches `activated`; browse a screen with photos; assert exactly three Cache Storage groups exist (`caches.keys()` includes the Serwist precache name, `wtw-api-data`, `wtw-photos`)

**Checkpoint**: A built app registers a working service worker with the full route table live and
provably present in Cache Storage. Every user story below builds on this.

---

## Phase 3: User Story 1 - Opening the app with no network shows the app, not a browser error (Priority: P1)

**Goal**: Cold offline reload renders the app shell; previously-fetched screens keep showing their
last-known data (offline banner visible); never-fetched screens show the screen's own empty/error
state, never a raw browser network error.

**Independent Test**: Load once online, go offline, force a full reload at any route — app shell
renders, not the browser's offline interstitial.

- [X] T010 [US1] In `frontend/app/sw.ts`, confirm/extend the class-1 navigation strategy so a full offline reload resolves to the precached shell rather than falling through to the browser's own offline page (tune `defaultCache`'s document handling or add an explicit `fallbacks.entries` document fallback if `defaultCache` doesn't already cover a zero-network navigation) — verified: `defaultCache`'s existing Next-aware rules already cover it, no explicit fallback needed
- [X] T011 [US1] `frontend/e2e-pwa/offline-cold-start.spec.ts` — three cases per spec.md Acceptance Scenarios: (1) load online once, go offline, reload → shell renders; (2) visit a data screen online, go offline, revisit it → last-known data + offline banner, no blank/error; (3) go offline, visit a screen never fetched this session → the screen's own empty/error affordance, not a raw network error, and no copy implying auto-recovery

**Checkpoint**: User Story 1 independently demoable — offline cold start works end to end.

---

## Phase 4: User Story 2 - Signing out leaves no trace of the previous user's cached data (Priority: P1)

**Goal**: Sign-out purges `wtw-api-data` and `wtw-photos`; a second user signing in on the same
device sees none of the first user's data, even offline.

**Independent Test**: Sign in, browse (populates both caches), sign out, sign in as someone else,
go offline — nothing of the first user is retrievable (DevTools Cache Storage + UI).

- [X] T012 [US2] Create `frontend/lib/auth/signOut.ts` — `signOutAndClearCache(supabase)`: calls `supabase.auth.signOut()`, then `caches.delete()` for both `USER_SCOPED_CACHE_NAMES` (guarded by `typeof caches !== "undefined"`)
- [X] T013 [P] [US2] `frontend/lib/auth/signOut.test.ts` — unit test with a mocked `caches` global: asserts both cache names are deleted and `signOut()` is called
- [X] T014 [US2] Update `frontend/app/(app)/profile/page.tsx`'s `handleSignOut` to call `signOutAndClearCache(supabase)` instead of `supabase.auth.signOut()` directly
- [X] T015 [US2] Update `frontend/components/auth/ResetPasswordForm.tsx`'s sign-out call the same way
- [X] T016 [US2] `frontend/e2e-pwa/sign-out-purge.spec.ts` — sign in as seeded user A, browse closet/outfits, sign out, assert `page.evaluate(() => caches.keys())` excludes both user-scoped cache names (precache still present); sign in as seeded user B, go offline, assert none of user A's item names/photos render

**Checkpoint**: User Story 2 independently demoable — the privacy-critical purge is provable in DevTools.

---

## Phase 5: User Story 3 - A signed photo URL that has expired never renders as a broken image (Priority: P2)

**Goal**: An `<img>` whose signed URL fails to load (expired token, unreachable, or deleted) always
falls back to the existing `NoPhoto` placeholder — never a native broken-image icon.

**Independent Test**: Force an image load failure on a previously-seen photo (offline, past TTL, or
mocked 400) — placeholder renders, not a broken-image glyph.

- [X] T017 [US3] Add an `onError` handler + `hasError` state to `frontend/components/ui/ItemPhoto/ItemPhoto.tsx` — on the `<img>` load failure, render `NoPhoto` the same way the `!src` branch already does
- [X] T018 [P] [US3] `frontend/components/ui/ItemPhoto/ItemPhoto.test.tsx` — unit test: render with a `src`, fire the image's `error` event, assert `NoPhoto`'s markup is now present and the broken `<img>` is gone
- [X] T019 [US3] `frontend/e2e-pwa/expired-photo.spec.ts` — load a screen with a photo whose signed URL is mocked to fail (400), assert the placeholder renders in the DOM; confirm no failure surfaces as a native broken-image render

**Checkpoint**: User Story 3 independently demoable.

---

## Phase 6: User Story 4 - The user is told when a new version of the app is ready, and can get it with one tap (Priority: P1)

**Goal**: On the client's next real reload after a deploy, a waiting service worker is detected and
a toast offers the update; accepting it actually runs the new version afterward.

**Independent Test**: Ship a change, do a full reload of an already-installed/open client, confirm
the toast, accept it, confirm the new build's code is what's now running.

- [X] T020 [US4] Create `frontend/lib/pwa/updateToastCopy.ts` — DRAFT-flagged copy constants (body "A new version is ready.", action label "Update now", dismiss `aria-label` "Dismiss") per `docs/design-decisions.md` §53; comment marks it unreviewed, single source
- [X] T021 [US4] Create `frontend/lib/pwa/useServiceWorkerUpdate.ts` — on mount, checks `registration.waiting`; attaches `updatefound`→`installed` listener for this navigation's own in-flight check (no polling, no `visibilitychange`, per `spec.md` Clarifications); exposes `{ updateAvailable, accept, dismiss }`; `accept()` posts `{type:"SKIP_WAITING"}` to the waiting worker and registers a one-time `controllerchange` → `location.reload()` listener first
- [X] T022 [US4] Add a `message` listener to `frontend/app/sw.ts` — `SKIP_WAITING` → `self.skipWaiting()` (`contracts/route-caching.md` message contract)
- [X] T023 [US4] Create `frontend/components/shell/UpdateToast.tsx` — uses `useServiceWorkerUpdate`; renders only when `updateAvailable`; `bottom: calc(90px + env(safe-area-inset-bottom))`, `z-index: var(--z-toast)`, slide-up + fade (`--motion-duration-base`/`--motion-easing-decelerate` in, `--motion-duration-fast`/`--motion-easing-accelerate` out), gated on `prefers-reduced-motion`; `role="status" aria-live="polite"`; body + "Update now" `Button` + close `IconButton` from `updateToastCopy.ts`
- [X] T024 [US4] Mount `<UpdateToast />` once in `frontend/app/layout.tsx` alongside `<ServiceWorkerRegistration />`
- [X] T025 [US4] `frontend/e2e-pwa/update-prompt.spec.ts` — build+start v1, register; rebuild with a detectable marker (e.g. a build-time env string rendered somewhere in dev-only markup) as v2, swap the served build, reload the still-open v1 page: assert the toast appears; click "Update now": assert `location.reload()` fires and the v2 marker is now present; separately, assert dismissing suppresses the toast without reloading, and it does not reappear on an in-app (client-side) navigation

**Checkpoint**: User Story 4 independently demoable — the brief's highest-risk item is proven end to end.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [X] T026 [P] Add iOS-only service-worker/cache items to `docs/ios-verification-backlog.md` (installed-PWA cache lifecycle, background/foreground reload behavior, Safari's more aggressive Cache Storage eviction under low disk — no physical iPhone available to verify any of it directly)
- [ ] T027 Run `npm run lint`, `npm run typecheck`, `npm test` (frontend) and confirm the existing dev-server `npm run e2e` suite is unaffected; fix any regressions
- [ ] T027a [P] Copy audit (FR-011/SC-006): grep every new/changed user-visible string this feature introduces (`updateToastCopy.ts`, any offline-related copy touched) for queue/retry/sync-promising language ("queued", "retry", "sync", "once you're back online") — zero matches expected; assert the exact toast copy in `update-prompt.spec.ts` (T025) as a regression guard
- [ ] T028 Run `quickstart.md`'s manual DevTools pass at `localhost:3000` and `127.0.0.1:3000`, both themes, **and** in installed/standalone display mode (FR-013 — `chrome://apps` install or DevTools' "Emulate a focused page" + `display-mode: standalone` media override) — record what was actually observed in Cache Storage (not just that a strategy was configured), per the handoff's explicit instruction
- [ ] T029 Full CI-equivalent check: backend `ruff`, `ruff format --check`, `mypy src`, `pytest`, `lint-imports` (expect unchanged — no backend files touched) and frontend `eslint`, `tsc --noEmit`, `next build`; confirm backend test count ≥753 and frontend test count ≥313 (handoff §7)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies
- **Foundational (Phase 2)**: depends on Setup — blocks every user story
- **User Stories (Phases 3–6)**: all depend on Foundational; independently testable once it's done, but see priority note below
- **Polish (Phase 7)**: depends on all four user stories being complete

### User Story Dependencies

- **US1, US2, US4 (P1)**: no dependency on each other — each builds on Foundational's route table/registration independently
- **US3 (P2)**: no dependency on the others either, but naturally follows US1 (offline browsing is what makes an expired-URL-while-offline scenario observable)

### Within Each Story

- Implementation before its own e2e spec (the spec needs something real to assert against)
- T014/T015 (US2's two call-site updates) depend on T012 (the helper they call)
- T023/T024 (US4's toast) depend on T020–T022 (copy + hook + SW message listener)

### Parallel Opportunities

- T002 (cache names), T005 (registration component), T007 (Playwright config), T008 (cache-names unit test) can all run in parallel once T001 lands
- T013 (US2 unit test), T018 (US3 unit test) can run in parallel with their story's other tasks once the thing they test exists
- US1, US2, and US4's *implementation* tasks (not their shared `sw.ts`/`layout.tsx` edits, which serialize) can proceed in parallel across different engineers once Foundational's checkpoint is reached — in a single-session build, sequential in priority order is simpler and avoids repeated edits to the same shared files (`sw.ts`, `layout.tsx`)

---

## Implementation Strategy

### Not a single-story MVP — US1 and US2 ship together

The generic "MVP = just the first story" pattern doesn't fit here: `spec.md` deliberately gives
User Story 1 (offline caching) and User Story 2 (sign-out purge) **equal P1 priority** because
shipping the first without the second is a privacy regression, not a smaller MVP (handoff §3.1,
`research.md` R5). The minimum defensible increment is **Foundational + US1 + US2** together. US4
(update prompt) is equally P1 for a different reason — the brief's highest technical risk — and
should not be deferred past the same initial pass, since a service worker shipped without a proven
update path is the thing most likely to require an emergency fix later that can't reach clients.
US3 (expired photo) is the one story that could genuinely ship a cycle later without harm (a rare
visual glitch, not a privacy or shipping-safety issue) if time-constrained.

### Recommended order

1. Setup → Foundational (checkpoint: SW registers, route table live, provable in Cache Storage)
2. US1 → US2 (checkpoint: offline browsing works AND is provably purged at sign-out)
3. US4 (checkpoint: an old client can be pushed onto a new version — the highest-risk item proven early, not left to the end)
4. US3 (checkpoint: no broken-image regression)
5. Polish
