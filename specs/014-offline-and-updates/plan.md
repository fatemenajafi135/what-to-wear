# Implementation Plan: Offline, caching and the update prompt

**Branch**: `feat/014-offline-and-updates` | **Date**: 2026-08-05 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/014-offline-and-updates/spec.md`

## Summary

Wires Serwist into the Next.js build (`injectManifest` mode) so the app has a real service worker
for the first time. Five request classes each get a deliberate strategy (`research.md` R3): the
app shell (same-origin, no user data — safe to precache/cache unconditionally), backend API reads
(`NetworkFirst`, purged at sign-out), backend API writes including the billed
`POST /recommend/messages` (`NetworkOnly`, explicit, never cached), and signed photo images
(`CacheFirst` with an expiration window matching the backend's own signed-URL TTL, purged at
sign-out). An `onError` fallback in the one shared `ItemPhoto` component — not a caching trick —
is what actually guarantees an expired photo never renders broken (R6). The update prompt is
reload-triggered only, per `/speckit-clarify`: no foreground polling, no `visibilitychange`
listener; a waiting worker is detected on the client's next real navigation, and accepting it
`postMessage`s `SKIP_WAITING`, which drives `self.skipWaiting()` + `clientsClaim` + a one-time
`controllerchange` reload. The toast's copy has no design-system entry — drafted once, flagged, and
routed to the design owner (`design-decisions.md` §53), per the §51 precedent.

## Technical Context

**Language/Version**: TypeScript 5.9.3 — frontend-only feature, no backend/Python change.

**Primary Dependencies**: `serwist` + `@serwist/next` (9.5.12, latest non-preview — `research.md`
R2) added new. Everything else already in `package.json` (Next 16.2.12, React 19.2.8,
`@playwright/test` 1.62.0 for the new production-build e2e suite, `@supabase/supabase-js` for the
existing sign-out call sites this feature wraps).

**Storage**: Browser `CacheStorage` (via Serwist/Workbox strategy classes) — no Postgres schema
change, no migration (confirmed against the handoff header: "Migration number: none expected").

**Testing**: Vitest (existing, for `cacheNames.ts`/`signOut.ts`/`ItemPhoto.tsx`-level unit tests —
anything that doesn't require a real service worker) + a **second** Playwright config,
`playwright.pwa.config.ts` running `next build && next start`, for everything that does
(`research.md` R9) — precache population, offline navigation, sign-out purge observed via
`caches.keys()`, and the full update/skip-waiting round trip.

**Target Platform**: unchanged — Vercel (frontend) / Railway (backend), one Next.js codebase
serving the desktop web experience and the installed mobile PWA (Principle IX). This feature adds
no platform-specific branch; `FR-013` requires identical behavior across all four browser-tab ×
installed-standalone / mobile × desktop combinations already established by feature 001.

**Project Type**: web application (existing `frontend/` + `backend/` split; this feature touches
only `frontend/`).

**Performance Goals**: a returning user's offline cold start renders in about the same time as an
online shell load (`SC-001`) — the precache is populated in the background on a prior visit, not on
the offline load itself. No numeric SLA beyond that; this feature adds no server-side latency
surface (no backend change at all).

**Constraints**: `POST /recommend/messages` must never be cached or auto-retried under any
circumstance (billed, non-idempotent — handoff trap #3); no cache may survive sign-out if it could
hold authenticated data (trap #2); no copy may promise queueing/retry (trap #4, `deferred-work.md`
#7 stays out of scope); service-worker behavior is only observable in a production build
(`research.md` R9), so dev-server-only verification is not sufficient for this feature's Definition
of Done.

**Scale/Scope**: one new service worker source file, one new Next-config wrapper, one small
cache-name constants module, one sign-out helper (used at 2 existing call sites), one
update-detection hook + one toast component + one draft-copy module, one `ItemPhoto.tsx` edit, and
a new `e2e-pwa/` Playwright suite. No new screens, no new backend routes, no new database table.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** N/A — no backend change at all; `pipeline/`,
      `retrieval/`, `scoring/`, `ingest/`, the knowledge base and the eval harness are untouched.
      The one place this feature's *rule* touches the AI surface is negative: it must guarantee
      `POST /recommend/messages` (the pipeline's entry point) is never cached or auto-retried by the
      service worker — enforced by an explicit `NetworkOnly` route (`research.md` R3/R4), not by
      touching the route's own implementation.
- [x] **II — Deterministic scoring.** N/A — no scoring code exists in this feature's scope.
- [x] **III — Style gates wardrobe.** N/A — no retrieval call is added, modified, or cached
      differently than any other API read.
- [x] **IV — Grounded output.** N/A — no outfit-generation or citation logic touched.
- [x] **V — Scorers are eval metrics.** N/A — no quality judgment introduced.
- [x] **VI — Schema stability.** N/A — no taxonomy, formality scale, or category group touched;
      this feature reads and caches existing API response shapes verbatim, it does not reshape them.
- [x] **VII — Contracts.** No new backend endpoint, so no OpenAPI regeneration needed. This
      feature's own internal contract (`contracts/route-caching.md` — which route class maps to
      which strategy/cache name, and the `SKIP_WAITING` message shape) is documented the same way a
      public contract would be, even though it's frontend-internal, so a reviewer or test can check
      it without reading all of `sw.ts`.
- [x] **VIII — Visual truth.** The update toast's placement (`bottom: calc(90px +
      env(safe-area-inset-bottom))`), stacking (`z-index: var(--z-toast)`), and motion
      (`var(--motion-duration-base)`/`var(--motion-easing-decelerate)` in,
      `var(--motion-duration-fast)`/`var(--motion-easing-accelerate)` out, gated on
      `prefers-reduced-motion`) all come from tokens already named in `design-system.md` §7/"BottomSheet
      & toast motion" — nothing new invented. **Copy is the one gap**: no key exists anywhere in
      `design-system.md`'s copy tables for this string. Handled exactly as Principle VIII requires
      for that situation (and as `design-decisions.md` §51 precedent models): drafted once, in one
      file (`lib/pwa/updateToastCopy.ts`), unmistakably flagged as a draft, recorded in
      `design-decisions.md` §53, routed to the design owner — not invented silently and shipped as
      if final. No code is copied from `design/prototype/` (there is nothing to copy from — §7
      itself says the toast has no built prototype markup to extract from). Loading/empty/error/
      offline states: this feature doesn't add a new *screen*, so no new state matrix is owed: it
      extends the *existing* offline banner's reach (via caching, not new UI) and adds one new
      transient toast, which itself has only two states (visible/dismissed) rather than the
      loading/empty/error/offline set that applies to data-bearing screens. Accessibility: the toast
      gets `role="status" aria-live="polite"` (same pattern as `Banner.tsx`, not a modal — no focus
      trap needed since it doesn't block interaction with the rest of the page), a real
      `:focus-visible` ring on its two controls (inherited from existing `Button`/`IconButton`,
      unmodified), and a 44px hit target on the close `IconButton` (existing component, unmodified
      default). `prefers-reduced-motion` is gated per FR-009/the Acceptance Scenarios.
- [x] **IX — One codebase.** No new route, no user-agent branching, no separate mobile build. The
      cache strategy and update-prompt logic run identically whether the current `display-mode` is
      `browser` or `standalone` (FR-013) — Serwist's service-worker registration is
      display-mode-agnostic by nature (it's a page-level API, not a chrome-level one), so there is no
      code path to diverge in the first place.
- [x] **X — Documents are data.** N/A — no document or corpus content added; `research.md` and
      `design-decisions.md` entries are project documentation, not RAG-indexed source material.

No unresolved gate. Complexity Tracking is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/014-offline-and-updates/
├── plan.md              # this file
├── research.md          # Phase 0 — done
├── data-model.md         # Phase 1 — done
├── quickstart.md         # Phase 1 — done
├── contracts/
│   └── route-caching.md
└── tasks.md              # Phase 2 (/speckit-tasks) — not yet generated
```

### Source Code (repository root)

```text
frontend/
├── next.config.ts                              # CHANGED — wrapped in withSerwistInit
├── app/
│   ├── sw.ts                                    # NEW — Serwist service worker source
│   │                                             #   (injectManifest entry point)
│   └── layout.tsx                               # CHANGED — mounts <ServiceWorkerRegistration />
│                                                 #   and <UpdateToast /> once, root shell
├── components/shell/
│   ├── ServiceWorkerRegistration.tsx             # NEW — registers app/sw.ts on mount
│   └── UpdateToast.tsx                           # NEW — the toast; uses useServiceWorkerUpdate
├── lib/
│   ├── serviceWorker/
│   │   └── cacheNames.ts                        # NEW — API_DATA_CACHE, PHOTOS_CACHE,
│   │                                             #   USER_SCOPED_CACHE_NAMES (data-model.md)
│   ├── pwa/
│   │   ├── useServiceWorkerUpdate.ts             # NEW — registration/waiting/postMessage logic
│   │   └── updateToastCopy.ts                    # NEW — DRAFT-flagged copy, single source (§53)
│   └── auth/
│       └── signOut.ts                            # NEW — signOutAndClearCache() wraps
│                                                 #   supabase.auth.signOut() + cache purge
├── components/ui/ItemPhoto/
│   └── ItemPhoto.tsx                             # CHANGED — onError → NoPhoto fallback (R6)
├── app/(app)/profile/page.tsx                    # CHANGED — handleSignOut uses signOutAndClearCache
├── components/auth/ResetPasswordForm.tsx         # CHANGED — same
├── .gitignore                                    # UNCHANGED — sw.js/workbox-*.js/swe-worker-*.js
│                                                 #   already listed (feature 001 anticipated this)
├── playwright.pwa.config.ts                      # NEW — build+start config for SW-dependent e2e
├── e2e-pwa/
│   ├── offline-cold-start.spec.ts                # NEW — User Story 1
│   ├── sign-out-purge.spec.ts                    # NEW — User Story 2
│   ├── expired-photo.spec.ts                     # NEW — User Story 3
│   └── update-prompt.spec.ts                     # NEW — User Story 4
├── lib/serviceWorker/cacheNames.test.ts          # NEW — unit
├── lib/auth/signOut.test.ts                       # NEW — unit
└── components/ui/ItemPhoto/ItemPhoto.test.tsx    # NEW — unit (onError path); component had no
                                                  #   test file before this feature

docs/
├── design-decisions.md                           # CHANGED — §52 (cache strategy + sign-out purge),
│                                                 #   §53 (update-prompt detection + draft copy)
└── ios-verification-backlog.md                   # CHANGED — new entries for SW/cache behavior
                                                  #   that can only be verified on real iOS
```

**Structure Decision**: every file sits inside the fixed layout (`frontend/`, `docs/`). No backend
change, no `infra/` change, no new top-level directory. `pipeline/`, `scoring/`, `retrieval/` are
untouched (nothing in this list is a Python file). The two existing PWA files this feature must
*not* rebuild — `app/manifest.ts`, `components/shell/OfflineBanner.tsx`,
`lib/useOnlineStatus.ts` — are deliberately absent from the CHANGED list above.

## Complexity Tracking

*No entries — no Constitution Check gate required a justified exception.*
