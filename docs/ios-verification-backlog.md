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

### From features 014 / 015 — offline and install *(anticipated)*

| # | What to check | Why it cannot be checked now |
|---|---|---|
| 9 | **The iOS manual "Add to Home Screen" card** across Safari, Chrome, Firefox, Edge and DuckDuckGo — each has a different Share entry point and needs its own copy. | Five real browsers on a real device. |
| 10 | **Apple splash screens** render at the right sizes without letterboxing. | Only visible on cold launch of an installed app. |
| 11 | **Service worker update prompt** appears after a deploy, and `skipWaiting` does not serve a stale build. | iOS service-worker lifecycle differs from Chrome's. |
| 12 | **Storage quota.** iOS quotas are tighter than Chrome's and eviction behaviour differs — relevant once real item photos are cached. | Needs a device with real data. |

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
