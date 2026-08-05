# Handoff — Feature 014: Offline, caching and the update prompt

**From:** tech lead · **Status:** ready to start · **Branch:** `feat/014-offline-and-updates`,
cut from `rebuild` · **Migration number: none expected** ·
**`design-decisions.md` sections start at `## 52`**

**Run this alone.** A service worker changes how every request in the app behaves.

---

## 1. Mission

**The app keeps working when the network doesn't, and tells me when a new version is ready.**

There is no service worker at all today — `frontend/` has no `sw.ts`, and Serwist is not
installed. Every asset and every request goes to the network, every time.

---

## 2. What 001 already shipped — do not rebuild it

`known-gaps.md` §-2 describes a long list of missing PWA surfaces, but it documents the
**prototype**, not this codebase. Verified against the repo today:

| | Status |
|---|---|
| `manifest` with shortcuts + maskable icon | **Done** — `frontend/app/manifest.ts` |
| Per-mode `theme-color` (light/dark) | **Done** — `app/layout.tsx` |
| `env(safe-area-inset-*)` on sticky/fixed chrome | **Done** — TopHeader, TabBar, composer, primers |
| Offline banner + `navigator.onLine` wiring | **Done** — `components/shell/OfflineBanner`, `lib/useOnlineStatus.ts` |
| Serwist / service worker / caching | **None of it exists.** This slice. |
| Update prompt | **Does not exist.** This slice. |

`.gitignore` already excludes `public/sw.js`, `public/swe-worker-*.js` and `public/workbox-*.js`
— 001 anticipated this slice. Build artifacts stay ignored.

---

## 3. Two gaps, and the first one is the whole slice

### 3.1 No cache strategy is specified anywhere, and this app is a hard case

The feature plan says "per-screen cache strategies." Neither `design-system.md` nor
`known-gaps.md` says what they should be. That is yours to decide, and it is not a routine
Serwist config, because of what this app's data actually is:

- **Almost every response is user-scoped and authenticated.** Caching them puts one user's
  closet, outfits and conversations in a device-level cache. **What happens on sign-out?** A
  cache that survives it is a real privacy problem, not a stale-data annoyance.
- **Photo URLs expire.** `wtw_photo_signed_url_ttl_seconds` is 3600, and the URL itself carries
  a token. Cache the *response* and you cache a URL that 404s an hour later; cache the *image*
  and the cache key is a URL that never repeats. Both fail differently. Decide deliberately.
- **The styling pipeline is expensive and non-idempotent.** A replayed `POST` is a second billed
  LLM call. Nothing about it should be cached or retried automatically.

Design-system §6 sets the boundary you are working inside: offline is **display-only** today —
the banner shows, specific actions disable, and *"nothing is queued for retry… no promise of
'we'll upload once you're back' is made in copy, because no such mechanism exists yet."*

**Queueing is out of scope** (`docs/deferred-work.md` #7). If you conclude it belongs here, say
so and stop — do not build it, and do not add copy that implies it.

Record the strategy per route class — §52 — with what you rejected. "Everything
`NetworkFirst`" is a decision too, and needs the same justification as anything else.

### 3.2 The update prompt has no copy

Everything about it is specified except the words:

- Anchored `bottom: calc(90px + env(safe-area-inset-bottom))` — **not** `bottom: 0`. The 90px is
  TabBar's total height, already including the FAB's upward protrusion.
- `z-index: var(--z-toast)` (50, already reserved). The offline `Banner` stays `sticky; top: 0;
  z-index: var(--z-sticky)` (10) — opposite edges, no stacking conflict.
- Motion: slide up from `translateY(100%)` + fade in, `var(--motion-duration-base)
  var(--motion-easing-decelerate)`; dismissal reverses at `var(--motion-duration-fast)
  var(--motion-easing-accelerate)`. Gate on `prefers-reduced-motion`.

**No copy key exists for it** in any of design-system's copy tables. Principle VIII forbids
inventing UI copy in code, so this is the same situation feature 016 hit: draft the line, keep
it in one place, flag it clearly, and ask the design owner. See `design-decisions.md` §51 for
how that was resolved there and what it does *not* license — a toast label is fixed copy, not
something a model writes.

Also: **no toast component exists.** `design-system.md` §8 records that the prototype had none,
so its motion spec above is a recommendation rather than an extraction from built code.

---

## 4. In scope

- Serwist, wired into the Next build. Artifacts stay gitignored.
- A cache strategy per route class, per §3.1, with sign-out purge decided and implemented.
- App-shell precaching so a cold offline start renders chrome rather than the browser's error
  page.
- The update prompt: detect a waiting service worker, show the toast, and reload into the new
  version on accept.
- `prefers-reduced-motion` gating on the toast.
- **iOS items go in `docs/ios-verification-backlog.md`**, not in a completion report. That file
  exists so "we couldn't test it" never becomes "we forgot about it," and this slice will
  generate several — installed-PWA cache behaviour differs on iOS.

## 5. Explicitly out of scope

Offline queueing / Background Sync (`deferred-work.md` #7) · `beforeinstallprompt`, the iOS
manual-install card, permission primers and splash screens (**015**) · push notifications · any
backend change · any change to `pipeline/`, `scoring/` or `retrieval/`.

---

## 6. Traps

1. **A service worker is sticky.** A bad one is cached on the client and can outlive the fix.
   Get the update/skip-waiting path right early, and verify you can ship a change that actually
   reaches an already-installed client.
2. **Never cache an authenticated response past sign-out.** §3.1.
3. **Never cache or auto-retry `POST /recommend/messages`** — it is billed and non-idempotent.
4. **Do not add copy promising offline retry.** Nothing queues; the copy convention says so
   deliberately.
5. **Do not rebuild 001's manifest, theme-color or safe-area work.** §2.
6. **Do not change pipeline behaviour** — `docs/eval-baselines/` holds three iterations of
   recorded work.
7. **`design/prototype/` is reference only; `../app-legacy` is read-only.** Note the prototype's
   status-bar `z-index: 1000` is scaffolding with no real-device equivalent — `known-gaps.md`
   says explicitly not to port it.

---

## 7. Definition of done

- [ ] With the network off, a cold start renders the app shell rather than the browser's offline
      page.
- [ ] Cached data is scoped per user and **gone after sign-out** — verified by signing out,
      signing in as someone else, and finding nothing of the first user's.
- [ ] A photo whose signed URL has expired does not render a broken image from cache.
- [ ] Deploying a change surfaces the update prompt on an already-installed client, and
      accepting it loads the new version.
- [ ] The toast sits above the TabBar with safe-area applied, at `--z-toast`, and does not fight
      the offline banner.
- [ ] Motion respects `prefers-reduced-motion`.
- [ ] No copy anywhere promises that anything is queued or will be retried.
- [ ] Backend test count has not dropped (**753** on `rebuild` today).
- [ ] Frontend test count has not dropped (**313** today).
- [ ] `ruff`, `ruff format --check`, `mypy src`, `pytest`, `lint-imports`, `eslint`,
      `tsc --noEmit`, `next build` all clean.
- [ ] iOS-specific items added to `docs/ios-verification-backlog.md`.
- [ ] **Checked in a browser** at `localhost:3000` *and* `127.0.0.1:3000`, both themes — and
      with DevTools offline, which is the only way most of this is observable at all.

---

## 8. If you hit a gap

Start new `design-decisions.md` sections at **`## 52`**. §51 is the most recent; `deferred-work.md`
lists what is parked and deliberately not yours.

Named decisions: the cache strategy per route class and the sign-out purge (§3.1), and the
update-prompt copy (§3.2).

The failure mode to guard against in `research.md` is not weak reasoning — it is an **incomplete
option list**. §37 exists because §28 was well-argued, correctly rejected the two options it
considered, and never considered the third.

And the one this project keeps relearning: **check what actually happened, not that the call
returned.** Four defects shipped because a value was accepted with a 2xx and then dropped or
defaulted. For a service worker the equivalent is: open the Application panel and look at what
is actually in the cache, rather than trusting that a strategy was configured.

---

## 9. Report back with

What you built · the cache strategy per route class and why · what happens to cached data on
sign-out, and how you proved it · how you verified an update reaches an already-installed client
· whether you received update-prompt copy or shipped a flagged draft · what you added to the iOS
backlog · the §7 results · **what you saw with DevTools offline.**

**Name what you skipped.**
