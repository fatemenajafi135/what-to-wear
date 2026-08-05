# Quickstart: validating offline, caching and the update prompt

Every behavior here requires a **production build with a real registered service worker**
(`research.md` R9) — `next dev` disables Serwist by design. Two verification paths: automated
(`e2e-pwa/`) and manual DevTools (required regardless — `known-gaps.md`/the handoff both call out
that a service worker's actual cache contents must be *observed*, not inferred from config).

## Setup

```bash
cd frontend
npm run build
npm run start -- -p 3200   # or: npm run e2e:pwa, which does build+start+test together
```

Backend must be running too (`cd backend && uv run uvicorn whattowear.main:app --reload`) with a
seeded user who has at least one closet item with a photo, so signed-URL and offline-data
scenarios have something real to exercise.

## Automated (`npm run e2e:pwa`)

Runs `playwright.pwa.config.ts` against the built app:

1. **Cold offline start (User Story 1)**: load the app once online (populates the precache and
   `wtw-api-data`), go offline (`context.setOffline(true)`), reload, assert the app shell renders
   (TabBar, header) rather than `chrome-error://`/Playwright's navigation failure.
2. **Sign-out purge (User Story 2)**: sign in, browse closet/outfits so `wtw-api-data` and
   `wtw-photos` populate, sign out, assert via `page.evaluate(() => caches.keys())` that neither
   cache name exists; sign in as a second seeded user, go offline, assert none of the first user's
   item names/photos appear.
3. **Expired photo → no broken image (User Story 3)**: seed a `photo_url` whose token is already
   expired (or mock the storage response to 400), load the item, assert the rendered DOM shows the
   `NoPhoto` placeholder, not a `<img>` with a failed natural size / no `broken-image` alt fallback
   rendered by the browser.
4. **Update prompt (User Story 4)**: build and start the app once, register the SW, then rebuild
   with a trivial source change (a marker string), start a second server instance on the same
   `swSrc` output path (or swap the built `.next` output the running server serves — whichever
   Serwist's own update-testing pattern makes simplest), reload the existing page, assert the
   toast appears; click "Update now"; assert `location.reload()` fires and the marker string from
   the new build is now present in the DOM.

## Manual DevTools pass (required — do this even if the automated suite is green)

1. **Application → Service Workers**: confirm one worker is `activated and is running`, `Update on
   reload` unchecked (that checkbox would defeat the reload-triggered detection this feature
   relies on being observable).
2. **Application → Cache Storage**: after browsing signed-in, confirm exactly three cache groups
   exist — the Serwist/Workbox precache, `wtw-api-data`, `wtw-photos` — and open each to see real
   entries (URLs, response bodies for a couple of API caches, image previews for `wtw-photos`).
3. **Sign out, then re-check Cache Storage**: `wtw-api-data` and `wtw-photos` must be gone
   entirely (not present-but-empty — the cache itself should no longer be listed). The Serwist
   precache must still be present.
4. **Network tab → Offline checkbox**: reload; app shell renders. Navigate to a previously-visited
   screen; its last-known data renders with the offline banner visible. Navigate to a screen never
   visited this session; its normal empty/error state renders, no raw Chrome offline page.
5. **Deploy a change, keep the tab open, then trigger the toast**: since detection is
   reload-triggered (no polling), a plain in-app navigation will **not** show it — do a real
   reload/back-navigation after the new build is live, confirm the toast appears at
   `bottom: calc(90px + env(safe-area-inset-bottom))`, `z-index: 50`, doesn't collide with the
   offline banner if both are triggered together (toggle Network offline while the toast is
   showing), and respects `prefers-reduced-motion` (DevTools → Rendering → Emulate CSS
   media feature `prefers-reduced-motion: reduce`).
6. **Both themes, both hosts**: repeat the toast/offline checks at `localhost:3200` and
   `127.0.0.1:3200`, light and dark (`prefers-color-scheme` emulation), per the handoff's §7
   checklist.

## What this quickstart does not cover

iOS/Safari-specific service-worker and installed-PWA cache quirks — no physical iPhone is
available to this project (`docs/ios-verification-backlog.md`); those items are recorded there,
not verified here.
