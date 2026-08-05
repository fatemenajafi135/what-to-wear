# Research: Offline, caching and the update prompt

## R1. What actually carries user data, and where

Traced before choosing any cache strategy, because it changes the whole shape of the problem:

- Every `app/**/page.tsx` under `(app)/` is a **plain server component with no data fetching**
  (confirmed: `ClosetPage`, `AppLayout`, etc. — no `fetch`, no cookies read, no Supabase server
  client call). All real data comes from `"use client"` components (`ClosetGrid.tsx` and siblings)
  that call `apiClient` (`lib/api/client.ts`), which hits `NEXT_PUBLIC_API_URL` — a **separate
  origin** from the Next.js app itself in production (Vercel frontend, Railway backend; only
  coincidentally the same host in local dev).
- **Consequence**: the Next.js app's own HTML/RSC navigation payloads and static assets contain
  zero user-scoped data. Precaching and caching them is unconditionally safe — no purge concern,
  no per-user variation to worry about.
- The only two request classes that carry user-scoped data are (a) calls to the FastAPI backend
  origin, and (b) signed photo URLs, which point at a **third origin** — Supabase Storage
  (`NEXT_PUBLIC_SUPABASE_URL`, e.g. `.../storage/v1/object/sign/...`).

This origin split is what the whole cache design below hangs off: same-origin traffic is one
strategy (safe, never purged), backend-API traffic is a second (user-scoped, purged), and
Storage-origin image traffic is a third (user-scoped bytes, purged, TTL-bounded).

## R2. Tooling: Serwist over hand-rolled `sw.ts` or Workbox CLI

**Decision**: `serwist` + `@serwist/next` (9.5.12, latest non-preview), `injectManifest` mode.

**Rationale**: the handoff names Serwist explicitly, and `.gitignore` already lists exactly the
artifact names this library produces (`public/sw.js`, `public/sw.js.map`,
`public/swe-worker-*.js`, `public/workbox-*.js`) — feature 001 already anticipated this choice.
`@serwist/next`'s `withSerwistInit` wraps the existing webpack production build (`next build` here
runs webpack, not Turbopack — no `--turbopack` flag on the `build` script or in `next.config.ts`)
and auto-generates the precache manifest from `.next/static` output, so the app-shell precache
that User Story 1 needs comes from the tool rather than a hand-maintained file list.
`@serwist/next/worker` also ships `defaultCache`, a Next.js-aware set of runtime-caching rules
(pages/RSC payloads, fonts, images, Next's own static chunks) already tuned for this framework —
used as the base and layered under this feature's own rules (order matters; first match wins).

**Alternatives considered**:
- *Hand-written `sw.ts` with the raw Cache API, no Workbox/Serwist primitives.* Rejected: reinvents
  precache-manifest generation, strategy classes, and the expiration/cache-name plumbing this
  feature needs anyway (NetworkFirst with timeout, an expiration plugin) — for no gain, since
  Serwist already produces `sw.js` under the exact filename the `.gitignore` entry was written for.
- *`next-pwa`.* Rejected: unmaintained (last real release predates Next's App Router being
  standard), and Serwist is its direct, actively-maintained successor built for App Router from
  the start.
- *Turbopack-based `injectManifest` via Next's newer bundler.* Not applicable — `next build` in
  this repo runs webpack today; revisit only if the project later opts into `--turbopack` for
  production builds.

## R3. Cache strategy per route class, and why "everything NetworkFirst" doesn't hold

Five distinct classes, each with a different correctness requirement — collapsing them into one
strategy would either break offline reads (their data is genuinely a network response, so
NetworkFirst is right) or risk caching something that must never be cached (the billed LLM call).

| # | Route class | Origin / match | Strategy | Cache name | Sign-out purge? |
|---|---|---|---|---|---|
| 1 | App shell: navigation (HTML/RSC), static build assets, fonts, manifest, icons | Same-origin (the Next app itself) | `defaultCache`'s existing Next-aware rules (precached at build + runtime NetworkFirst/StaleWhileRevalidate per asset type) | Serwist/Workbox defaults | **No** — contains no user data (R1) |
| 2 | Backend API reads (`GET /closet/*`, `/recommend/outfits*`, `/recommend/sessions*`, `/recommend/readiness`, `/calendar/*`, `/profile`, `/taxonomy/categories`) | Backend API origin, method `GET` | `NetworkFirst`, 4s network timeout, then cache | `wtw-api-data` | **Yes** |
| 3 | Backend API writes — every non-GET call to the API origin, explicitly including `POST /recommend/messages` | Backend API origin, method `POST`/`PATCH`/`PUT`/`DELETE` | `NetworkOnly` (explicit rule, not just "unmatched passthrough" — see R4) | n/a, nothing stored | n/a — nothing cached |
| 4 | Signed photo images | Supabase Storage origin (`NEXT_PUBLIC_SUPABASE_URL` + `/storage/v1/object/sign/`) | `CacheFirst` (the signed URL is immutable content for its lifetime — no reason to revalidate), `ExpirationPlugin({ maxEntries: 300, maxAgeSeconds: 3600 })` matching the backend's own `wtw_photo_signed_url_ttl_seconds` | `wtw-photos` | **Yes** |
| 5 | Reference/taxonomy data (`GET /taxonomy/categories`) | Backend API origin, method `GET`, but not user-scoped | Folded into class 2 today — same strategy, same cache. Not split out as its own class because the data volume is tiny (one small list) and the privacy cost of over-purging it (an extra network round-trip after sign-in) is negligible; a real win only appears at a scale this app isn't at. | `wtw-api-data` | Purged along with class 2 (accepted; see Rejected alternatives) |

**Why not "everything `NetworkFirst`"**: that single rule is actively wrong for class 3 (a repeat
`POST /recommend/messages` bills a second LLM call — NetworkFirst still lets the *first* attempt
through to the network and would be fine for a GET, but Workbox's `NetworkFirst` will fall back to
a cached POST response if one existed, which is the wrong failure mode entirely for a call that
must never be answered from cache) and wrong for class 1 (Next's static chunks are
content-hashed/immutable — NetworkFirst would re-fetch bytes that CacheFirst semantics already
guarantee are correct, wasting a request on every load for no freshness benefit).

**Rejected alternatives**:

| Option | Rejected because |
|---|---|
| **(a) chosen** — five-class table above | — |
| (b) Uniform `NetworkFirst` for every request the app makes | Breaks class 3's non-idempotence guarantee and wastes requests on class 1's immutable assets; "simple" only in the sense of being wrong in two different directions at once. |
| (c) `StaleWhileRevalidate` for photos (class 4) instead of `CacheFirst` | A signed URL's query-string token never changes for a given mint — revalidating it fetches the exact same bytes again. `StaleWhileRevalidate` earns its cost when the *same URL* can return different content over time; here a changed photo gets a **new** URL from the JSON response anyway, so the old cache entry is simply superseded, not revalidated. `CacheFirst` is cheaper with no correctness cost. |
| (d) Cache the API *response envelope* containing the photo URL, but not the image bytes themselves | Solves nothing on its own — the `<img>` tag still fetches the (possibly now-expired) URL from a network request the SW would either intercept (class 4, handled below) or let through and fail nakedly. Bytes still need their own strategy; this option just relocates the problem instead of resolving it. |
| (e) Split taxonomy into its own non-purged cache class | Correct in principle but not worth a sixth cache name and a second purge-exclusion branch for one small endpoint at this app's current scale — revisit if/when this list grows into something with real caching upside. |

## R4. Why an explicit `NetworkOnly` rule for POST/mutations, not just "let it fall through unmatched"

Serwist/Workbox's router already passes an unmatched request straight to `fetch()` with no
caching — functionally identical to an explicit `NetworkOnly` handler. The explicit rule is added
anyway because:
1. It makes the constraint ("never cache or retry the billed call") **visible in the route table**
   rather than relying on the absence of a rule, which is exactly the kind of thing that silently
   breaks the next time someone edits `runtimeCaching` and adds a broader catch-all.
2. It gives a single place to assert this in a test (a route-table unit test asserting the
   `/recommend/messages` matcher resolves to a `NetworkOnly` strategy, not "no rule found").

## R5. Sign-out purge mechanism

**Decision**: on sign-out, from the page (not via `postMessage` to the service worker), call
`caches.delete("wtw-api-data")` and `caches.delete("wtw-photos")` — the two cache names owned by
classes 2 and 4 above — before navigating to `/signin`. Implemented once in a shared
`signOutAndClearCache()` helper (`lib/auth/signOut.ts`), used by both existing sign-out call sites
(`app/(app)/profile/page.tsx`, `components/auth/ResetPasswordForm.tsx`) so the purge can't be added
to one call site and forgotten on the other.

**Rationale**: `caches` (the `CacheStorage` interface) is available on `window`, not just inside
the service worker — no message-passing round-trip needed, no risk of the purge racing a SW that
hasn't activated yet. Deliberately **not** a blanket "delete every cache": that would also delete
class 1's precache (the app shell), which is same-origin, contains no user data (R1), and — if
wiped — would leave the very next offline cold-start with nothing to render until a new service
worker install/activate cycle repopulates it (undermining User Story 1 for the next person to use
the device, signed in or not). Naming exactly two caches and deleting exactly those two is what
makes "purged, but only the caches that could hold a user's data" concretely provable in DevTools.

**Rejected alternatives**:

| Option | Rejected because |
|---|---|
| **(a) chosen** — delete `wtw-api-data` + `wtw-photos` by name, from the page | — |
| (b) `caches.keys().then(keys => Promise.all(keys.map(caches.delete)))` — delete everything | Also deletes the app-shell precache, breaking cold-start-offline for the very next session on that device until the SW reinstalls it. Over-broad for the privacy problem it's solving. |
| (c) `postMessage` to the service worker, purge inside `sw.ts` | No functional advantage here (`caches` is equally available in both contexts) and adds a message-passing round trip with its own failure mode (message sent before the SW controller exists yet, e.g. right after first install) for no benefit. |
| (d) Versioned/namespaced cache keys per user ID instead of a purge | Solves a different problem (multi-user *coexistence* in cache) that this app doesn't have — only one signed-in user's data should ever be retrievable at a time by design, so there's nothing to keep isolated *between* live sessions, only something to erase *between* them. Adds real complexity (every cache read/write now needs the current user ID threaded through) for a capability nobody asked for. |

## R6. Expired signed photo URL never renders broken — client-side fix, not a caching trick

**Decision**: `ItemPhoto.tsx` (the single component every photo render already funnels through —
verified: `ClosetGrid`, `OutfitsGrid`, closet/outfit detail pages, and `ItemThumbnailRow` all pass
`photo_url` into it, none render a raw `<img>` themselves) gets an `onError` handler on its
`<img>` that swaps to the existing `NoPhoto` placeholder — the same component already used when
`src` is falsy.

**Rationale**: this is the one fix that's correct regardless of *why* the URL failed — expired
signed-URL token (this feature's specific concern), Storage being briefly unreachable, or the
object having been deleted. The service worker's cache strategy (R3, class 4) governs whether
*previously-fetched* image bytes are available; it cannot know that a URL's embedded token has
"expired" — from an HTTP cache's perspective an expired signed URL is just a URL, indistinguishable
from any other, until the storage backend responds 400. The failure has to be caught where the
browser actually reports it: the `<img>` element's own `error` event.

**Rejected alternatives**:

| Option | Rejected because |
|---|---|
| **(a) chosen** — `onError` fallback inside `ItemPhoto` | — |
| (b) Have the service worker inspect cached API JSON, detect a stale `photo_url`, and rewrite the response before it reaches the page | No reliable way to know a token is expired without decoding Supabase's signed-URL format inside the SW (fragile, couples the SW to a Storage implementation detail) or making a network call to check — at which point it's simpler to just let the `<img>` request fail and handle that. |
| (c) Don't cache the JSON response at all if it contains a `photo_url` (avoid the problem by avoiding class 2 caching for those endpoints) | Throws out the offline-browsing story (User Story 1's acceptance scenario 2 — "previously-seen data is still visible") for every screen that has photos, which is most of them. The bug is narrower than the story it would sacrifice. |

## R7. Update detection and the toast

Per `/speckit-clarify` (2026-08-05): **reload-triggered only** — no foreground polling
(`setInterval` + `registration.update()`) and no `visibilitychange` listener. This matches
Serwist's own documented "reload prompt" recipe in its simplest form (the polling/visibility
additions are opt-in extras the recipe explicitly separates out) and is the form the design owner
chose when asked directly.

**Mechanics**: `skipWaiting: false` in the `Serwist` constructor (`app/sw.ts`) — the default, and
deliberately not overridden — means a new service worker that the browser's own navigation-time
update check installs sits in the `waiting` state rather than activating itself. A small
client-side hook (`lib/pwa/useServiceWorkerUpdate.ts`), mounted once in the root layout:
1. Registers the SW (`serwist-window`'s `Serwist` helper, or a direct `navigator.serviceWorker.register`).
2. On mount, checks `registration.waiting` — if already present (the browser's background check
   on *this very reload* already finished), a waiting worker exists immediately.
3. Also attaches an `updatefound` → `installed` listener on the current registration, to catch an
   in-flight check (started by this same navigation) that completes a moment after mount — still a
   single reload's worth of detection, not a new polling loop.
4. On accept, `postMessage({ type: "SKIP_WAITING" })` to the waiting worker; `sw.ts` listens for
   that message and calls `self.skipWaiting()`. `clientsClaim: true` plus a one-time
   `controllerchange` listener on the client then triggers `location.reload()` — this is what
   makes FR-008 true (the reload actually runs the new worker's code, not a refresh that re-serves
   the old cached shell under the old controller).

Per clarification, dismissing needs no persisted flag: since detection isn't re-run mid-session,
plain component state (reset naturally on the next real navigation) is sufficient — nothing to
store in `localStorage`, nothing that could leak across sign-out.

## R8. Update-prompt copy — drafted, not decided

No key exists in `design-system.md`'s copy tables (§6, §9) for this string, and Principle VIII
reserves inventing UI copy in code. Per the precedent in `docs/design-decisions.md` §51: draft it,
keep it in exactly one place, mark it unmistakably as a draft, and route it to the design owner —
this is not a case like §51's five model-written lines (this is fixed system copy, closer to the
offline banner than to a conversational reply), so the §51 exception for user-facing model output
doesn't apply here; this is ordinary Principle VIII copy that just hasn't been reviewed yet.

**Draft** (impersonal/system voice, per §9's exception for connection/sync state — matching the
existing offline banner's register, not the first-person stylist voice):
- Body: "A new version is ready."
- Action button: "Update now"
- Dismiss: an icon-only close control (`IconButton icon="close"` already exists in the catalog),
  `aria-label="Dismiss"`.

Recorded as `docs/design-decisions.md` §53, flagged as draft in the single source file
(`lib/pwa/updateToastCopy.ts`), pending the design owner's review — see that section for what this
does and doesn't license.

## R9. Testing a service worker: dev server can't do it

The existing `e2e/` suite runs against `next dev` (`playwright.config.ts`) — Serwist disables
service-worker registration in development by design (HMR and an unstable module graph are
fundamentally incompatible with a precache manifest), and the existing suite's own comment already
notes production-only behavior is out of its scope. Every behavior in this feature (precache
population, offline navigation, sign-out purge, the update/skip-waiting path) requires a **built
and served** app with a real, registered service worker.

**Decision**: a second Playwright config (`playwright.pwa.config.ts`) that runs `next build && next
start` on its own port, with its own `e2e-pwa/` test directory, run via a separate script
(`npm run e2e:pwa`) — kept out of the default `npm run e2e` / CI-fast-path so the existing suite's
fast dev-server iteration loop isn't slowed down by a full production build on every run, but
runnable on demand and specifically before this feature ships. CI runs both.

**Alternatives considered**:
- *Force the existing dev-server suite to also cover this, disabling Serwist's dev-mode guard.*
  Rejected — fighting a deliberate, documented safety guard in the tool to save one extra `webServer`
  block is a worse trade than just adding the block.
- *Skip automated browser coverage for this feature, rely on manual DevTools verification only.*
  Rejected per the handoff's explicit instruction: this environment can drive a real (headless)
  browser via Playwright (confirmed working), so there is no excuse to skip it — manual DevTools
  verification still happens too (see `quickstart.md`), but as a supplement, not a replacement.
