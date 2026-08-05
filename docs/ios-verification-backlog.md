# iOS verification backlog

**Development target: Android first.** No iPhone is available to this project yet, so every
iOS-specific behaviour is **built blind** — implemented to spec, verified by reading, and
recorded here until someone with a physical iPhone can check it.

This file exists so "we couldn't test it" never silently becomes "we forgot about it."

## How to use it

- **Every slice adds its iOS-only items here** rather than leaving them in a completion
  report that scrolls out of memory.
- Nothing is removed until it has been checked on a **physically installed** PWA on a real
  iPhone. Safari on a Mac is not a substitute — the storage isolation, the safe-area insets
  and the install flow only exist on the device, installed.
- An item that fails becomes a normal bug with a fix brief, not a re-litigation of the
  design.

## Why iOS differs at all

Two mechanisms cause almost everything in this file:

1. **Storage isolation.** An installed iOS PWA gets its own storage container, separate from
   Safari. Android's WebAPK shares Chrome's storage, so the whole class of bug does not
   exist there.
2. **No browser chrome.** Installed standalone means no URL bar and no back button, so
   in-app navigation and safe-area insets carry weight they never carry in a tab.

---

## Open items

### From feature 001 — app shell and PWA basics

| # | What to check | Why it cannot be checked now | Built to |
|---|---|---|---|
| 1 | **Safe-area insets on a notched device**, installed standalone. TabBar bottom padding, BottomSheet bottom padding, sticky header top inset. | `env(safe-area-inset-*)` resolves to `0` in a desktop browser and in a mobile browser tab. Only an installed app on a notched device reports real values. | `design/known-gaps.md` §-2 safe-area audit |
| 2 | **`display-mode: standalone` detection** and the four form-factor × display-mode combinations. | The installed-standalone half cannot be produced without installing on the device. | `design-system.md` §7 matrix |
| 3 | **Apple touch icon renders correctly** on the home screen — no black corners, no double rounding. | Only visible once added to the home screen. | 180×180, flattened, no alpha — verified programmatically |
| 4 | **No browser chrome means TopHeader's back button is the only way back.** Confirm no screen with history omits it. | The failure only manifests where there is no URL bar. | `design-system.md` §7 |

### From feature 003 — auth *(confirmed as built; still unverifiable without a device)*

| # | What to check | Why it cannot be checked now | Built to |
|---|---|---|---|
| 5 | **Google OAuth returns to the installed app**, not to Safari, and the session is present afterwards. | Requires installed-standalone on iOS. On Android this works via shared Chrome storage and proves nothing about iOS. **Additionally untested anywhere at all in this build** — no Google Cloud OAuth client credentials were available in the environment this slice was built in; the button is wired (`signInWithOAuth` + `/auth/callback` route handler) and the redirect URL is on Supabase's allow-list, but the actual provider round trip has never run. | `docs/design-decisions.md` §12, `specs/003-auth/plan.md` |
| 6 | **PKCE `code_verifier` survives the round trip** — the exchange must happen in the same storage container that started the flow. Failure looks like a generic OAuth error, not a storage bug. | Container isolation does not exist on Android. | §12 requirement 1 — implemented via `@supabase/ssr`'s cookie-based client (`flowType: 'pkce'`), not `localStorage` |
| 7 | **Password reset does not attempt a cross-container handoff.** After reset, the user lands on `/signin` and signs in inside the app. | Same reason. | §12 — confirmed: `ResetPasswordForm` calls `supabase.auth.signOut()` immediately after a successful `updateUser`, before showing the success state, so no session persists past the reset regardless of which container the link opened in |
| 8 | **Session survives app backgrounding and relaunch.** | iOS is more aggressive about evicting PWA storage than Android, and may suspend the Supabase client's background token-refresh timer while backgrounded. | Cookie-based session (`proxy.ts` refreshes on every server request via `updateSession`) plus the Supabase browser client's own `autoRefreshToken` — neither is iOS-specific, but iOS's suspension behavior around them is unverified |
| 13 | **The custom recovery email link** (`{{ .SiteURL }}/reset-password/{{ .TokenHash }}`, `specs/003-auth/research.md` §6) opens correctly from Apple Mail into the browser (not the installed app — that's item 7's guarantee, not a bug) on iOS specifically. | Apple Mail's link-handling and universal-links behavior differs from Android's. | `infra/supabase/templates/recovery.html` |

### From feature 012 — calendar *(confirmed as built; still unverifiable without a device)*

| # | What to check | Why it cannot be checked now | Built to |
|---|---|---|---|
| 14 | **Google Calendar OAuth returns to the installed app**, not to Safari, and the connection is present afterwards — the same container-isolation hazard as item 5, but for a second, independent OAuth flow (`/calendar/callback`, not `/auth/callback` — specs/012-calendar/research.md §1). **Also untested anywhere at all in this build**, same reason as item 5: no Google Cloud OAuth client credentials were available in the environment this slice was built in. The flow is fully wired (PKCE start/finish routes, `/calendar/callback` route handler, the redirect URI documented for the Google Cloud Console allow-list) but the actual provider round trip has never run. | Requires installed-standalone on iOS. On Android this works via shared Chrome storage and proves nothing about iOS. | `docs/design-decisions.md` §12, `specs/012-calendar/research.md` §1/§3 |
| 15 | **PKCE `code_verifier` survives the round trip** for the calendar flow specifically. Unlike item 6 (Supabase's `@supabase/ssr` cookie-based client), this flow's verifier is held server-side in `calendar_oauth_attempts`, keyed by an opaque `state` value the client only ever sees as an opaque redirect parameter — so container isolation should not be able to break it the way it can for a client-held verifier. Worth confirming on-device rather than assuming. | Requires installed-standalone on iOS to exercise the real redirect round trip. | `specs/012-calendar/research.md` §3 |
### From feature 013 — Profile & Settings *(confirmed as built; still unverifiable without a device)*

| # | What to check | Why it cannot be checked now | Built to |
|---|---|---|---|
| 14 | **Native `<input type="date">` picker UI** (Body & size → Birth date) — iOS Safari's date wheel, especially inside an installed PWA rather than a browser tab. | Only a real iOS device renders the native control's actual picker chrome; desktop/Android render entirely different pickers. | `docs/design-decisions.md` §1.5 — kept native deliberately |
| 15 | **Native `<select>` picker UI at this feature's specific option-list lengths** (Height: 21 options, Shoe size: 17, per `tasks.md` T021's own concrete arrays) — iOS's wheel picker at that length. | Same reason — iOS's picker chrome is unverifiable outside a device. | `docs/design-decisions.md` §1.4 |
| 16 | **`BodyShapePicker`'s horizontal-scroll drag** (5 options, momentum scroll) on real iOS touch. | Touch momentum/overscroll behavior differs from a desktop trackpad/mouse simulation. | `components/ui/BodyShapePicker/BodyShapePicker.tsx` |
| 17 | **`TagInput`'s Enter-to-commit on iOS's on-screen keyboard** (Style preferences → Brands to avoid) — whether the iOS "return" key reliably fires the same `keydown` Enter event a hardware keyboard does. | A known iOS Safari quirk area; unverifiable without a real on-screen keyboard. | `components/ui/TagInput/TagInput.tsx` (unchanged by this feature, first real usage of it) |

### From feature 015 — install *(anticipated, not yet built)*

| # | What to check | Why it cannot be checked now |
|---|---|---|
| 9 | **The iOS manual "Add to Home Screen" card** across Safari, Chrome, Firefox, Edge and DuckDuckGo — each has a different Share entry point and needs its own copy. | Five real browsers on a real device. |
| 10 | **Apple splash screens** render at the right sizes without letterboxing. | Only visible on cold launch of an installed app. |

### From feature 014 — offline, caching and the update prompt *(built and verified on Android/desktop Chrome; refines old items 11-12)*

| # | What to check | Why it cannot be checked now | Built to |
|---|---|---|---|
| 18 | **The update prompt's full lifecycle on WebKit** — does a new service worker reliably reach and stay in `waiting` the same way Chromium's does, does the `SKIP_WAITING` `postMessage` reliably reach it, and does `controllerchange` reliably fire before the forced `location.reload()`? Confirmed working on Chromium (`e2e-pwa/update-prompt.spec.ts`); WebKit's service-worker lifecycle has historically had its own quirks around exactly these transitions. | No WebKit engine available in this environment; Chromium-only automated coverage. | `lib/pwa/useServiceWorkerUpdate.ts`, `app/sw.ts` |
| 19 | **Opaque cross-origin responses actually get cached by `CacheFirst` + `CacheableResponsePlugin` on WebKit.** This feature's `wtw-photos` cache depends on it (`docs/design-decisions.md` §52) — older Safari/WebKit Cache API implementations have had bugs specifically around persisting opaque (`no-cors`) responses that Chromium didn't share. If this silently fails on iOS the way the *un-patched* `CacheFirst` config silently failed here (found only by inspecting real `Cache` contents, not by reading config), the symptom is a working-looking app that still re-fetches every photo. | WebKit-specific Cache API behavior, unverifiable outside a real WebKit engine. | `app/sw.ts` class 4 |
| 20 | **Cache Storage eviction under iOS storage pressure**, for an *installed* PWA specifically. iOS is known to evict a web app's storage more aggressively than desktop Chrome once the device is low on space — relevant to both `wtw-api-data` and `wtw-photos`, and to whether the app-shell precache itself can be silently cleared (which would regress cold-start-offline, User Story 1, without any code change). | Needs a real device under real storage pressure; unsimulatable. | `docs/design-decisions.md` §52 |
| 21 | **A true cold launch offline** (airplane mode, installed PWA, app fully killed then relaunched — not just a background/foreground cycle) renders the app shell. Chromium-equivalent proven (`e2e-pwa/offline-cold-start.spec.ts`), but iOS's own precache/document-fallback behavior on a genuine cold process start is unverified. | Requires a real installed PWA and a real airplane-mode cold launch. | spec.md User Story 1 |
| 22 | **Sign-out cache purge**, for an installed iOS PWA's own storage partition specifically. Same-origin `caches.delete()` should behave identically to Android per this file's own "storage isolation" framing, but worth confirming rather than assuming, given how central the privacy guarantee is (spec.md User Story 2). | Requires the device's own storage container. | `lib/auth/signOut.ts` |
| 23 | **Returning to an already-open PWA from the app switcher** — does iOS suspend-and-resume the page (no reload, so update detection per this feature's reload-triggered-only design never fires until an actual relaunch) or does it sometimes silently reload the page in the background (which *would* trigger a check)? This affects how often an installed iOS user is realistically offered an update, though not correctness — reload-triggered detection was chosen deliberately over polling (spec.md Clarifications) and this item is about iOS's specific suspend/resume behavior, not a reason to revisit that decision. | iOS's process-suspension behavior for installed web apps is not reproducible outside a device. | spec.md Clarifications, `docs/design-decisions.md` §53 |

---

## What Android *does* prove

Not everything needs a device. These are genuinely verified by testing on Android and do not
belong in this backlog:

- Responsive chrome across all three tiers, and identical routes at every width
- `beforeinstallprompt`, the Android install flow, and the installed WebAPK
- Service worker registration, caching strategy correctness, offline behaviour
- Every component's states, both themes, `prefers-color-scheme` boot resolution
- OAuth *mechanics* — that PKCE is wired correctly, the redirect allow-list is right, and
  the callback route works. **Only the storage-container behaviour is iOS-specific.**

That last point matters for scheduling: an OAuth bug found on Android is a real bug worth
fixing now. Passing on Android simply does not clear item 5.

---

## Before the iOS pass

When a device becomes available, give whoever has it:

1. This file.
2. A deployed URL — not a local dev server. Installing a PWA requires HTTPS and a real
   origin.
3. Instructions to **install to the home screen first**, then test. Everything above is
   about installed-standalone behaviour; testing in a Safari tab exercises none of it.

Expect real findings. Blind development to a written spec is a reasonable way to build this,
but it is not the same as having tested it, and this file should be read as a list of open
risks rather than a formality.
