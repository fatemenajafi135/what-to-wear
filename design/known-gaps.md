# Known gaps — implement in code

## -2. PWA surfaces — everything listed here needs real browser APIs
None of the install prompt, splash, icons, update toast, or permission primers described in the design spec exist as working code — this project has no `manifest.json`, no service worker, and no real camera/calendar API calls. To implement:
- **manifest.json** — full spec, not just colors:
  ```json
  {
    "name": "What to Wear",
    "short_name": "What to Wear",
    "id": "/",
    "start_url": "/?source=pwa",
    "scope": "/",
    "display": "standalone",
    "orientation": "portrait",
    "lang": "en-US",
    "dir": "ltr",
    "background_color": "#E6E1D6",
    "theme_color": "#4B2E52",
    "icons": [
      { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any" },
      { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any" },
      { "src": "/icons/icon-512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
    ],
    "shortcuts": [
      { "name": "Add an item", "short_name": "Add item", "url": "/?action=add", "icons": [{ "src": "/icons/shortcut-add.png", "sizes": "96x96", "type": "image/png" }] },
      { "name": "Get a recommendation", "short_name": "Recommend", "url": "/?action=recommend", "icons": [{ "src": "/icons/shortcut-recommend.png", "sizes": "96x96", "type": "image/png" }] }
    ]
  }
  ```
  Link via `<link rel="manifest" href="/manifest.json">`.
- **Per-mode status bar color**: manifest `theme_color` is static, so add BOTH of these in `<head>` (the browser picks the matching one live, unlike the manifest field):
  ```html
  <meta name="theme-color" media="(prefers-color-scheme: light)" content="#E6E1D6">
  <meta name="theme-color" media="(prefers-color-scheme: dark)" content="#1C1822">
  ```
  Using `--color-background` per mode (not `--color-primary`) because that's the color actually adjacent to the status bar in this app — every sticky header sits on `--color-background`, not on primary.
- **Cold-start flash / background_color**: can't media-query, so this is a fixed approximation. `#E6E1D6` (light) is the pragmatic pick given a self-inflicted constraint logged just below — NOT a fundamental limitation, just the current state of the code. Once that's fixed, re-evaluate; a static manifest color still can't fully solve it either way.
- **Theme not synced to system preference at boot (separate, real gap)**: `state.theme` always initializes to `'light'` regardless of OS preference — nothing reads `prefers-color-scheme` at boot. This is what makes the `background_color` choice above a workaround rather than a real fix. Implement: read `matchMedia('(prefers-color-scheme: dark)').matches` before first paint and seed `state.theme` from it (falling back to a persisted user override if they've used the in-app toggle before).
- **Status-bar overlay z-index is prototype-only scaffolding**: `ios-frame.jsx`'s simulated status bar (clock/signal/battery) carries an app-level `z-index:1000` so it outranks every in-app sticky header/tab-bar/toast within this prototype's DOM. That z-index has no real-device equivalent — on an actual device the OS compositor draws the status bar in its own layer above the entire web view; there is no app-level element and no z-index to set. Do not port this z-index rule into production code; it exists solely so the bezel mockup behaves like real OS chrome during prototyping.
- **Safe-area audit — every fixed/sticky offset needs checking against `env(safe-area-inset-*)`, not just the update toast**:
  - Update toast: `bottom: calc(90px + env(safe-area-inset-bottom))`, not a bare `90px`.
  - TabBar's own bottom padding is currently a hardcoded `22px` approximating home-indicator clearance — replace with `env(safe-area-inset-bottom, 22px)` so it reflects the real device value once installed instead of guessing a fixed number.
  - Every `BottomSheet.dc.html` instance (outfit menu, item menu, filter sheet — plus the new install-prompt/permission-primer cards, which are BottomSheet-style) has a fixed `30px` bottom padding with the same problem; same fix, `calc(30px + env(safe-area-inset-bottom))`.
  - Sticky screen headers now carry real top-inset padding (`env(safe-area-inset-top)`, unioned in the prototype with a `--wtw-proto-inset-top` custom property — declared once, `64px`, alongside the other layout tokens near the top of the file — that simulates the bezel's status bar). **On ship, delete `--wtw-proto-inset-top` and its `max()` wrapping; production headers use bare `env(safe-area-inset-top)`** — a real device's own inset is correct with no floor, and adding one back would push every header down by a fixed amount that has nothing to do with the actual notch/inset. This only matters if the app adopts `<meta name="viewport" content="viewport-fit=cover">` for edge-to-edge status-bar theming — without that meta the OS excludes the status-bar area from the web viewport already and `env()` reports 0.
  - The theme toggle and dev-override panel (`top:20px`/`left:20px`/`right:20px`) are prototype-only chrome already flagged for removal (§-1) — excluded from this audit.
- **Icon assets**: export actual PNGs at 192, 512, maskable 512 (glyph confined to the inner 80%-diameter safe circle — the maskable version needs real padding baked in, not a reused flat icon), apple-touch-icon 180 (flattened, no transparency), favicon 32/16, plus the two 96×96 shortcut icons referenced in the manifest above.
- **Install prompt (Android/Chrome) — gating is strict**: capture `beforeinstallprompt` on `window` (`event.preventDefault()`, store it as `deferredPrompt`). Visibility condition: `deferredPrompt !== null && <engagement trigger met> && !<dismissed within cooldown> && !isStandalone` — if the event never fires, `deferredPrompt` stays `null` forever and **the card must not render at all**, regardless of engagement trigger. On accept, `deferredPrompt.prompt()`; listen for `appinstalled` to suppress permanently after. Check `window.matchMedia('(display-mode: standalone)').matches` on load.
- **iOS manual card — per-browser instructions, not Safari-only**: since iOS 16.4, Chrome, Firefox, Edge, DuckDuckGo, and others support Add to Home Screen too — show the card to all of them, with copy/icon-position branched per browser (the Share entry point differs):
  - **Safari**: Share icon, bottom center of the toolbar → "Add to Home Screen" → Add.
  - **Chrome, DuckDuckGo**: Share/menu icon, top right → "Add to Home Screen" (Chrome may label it "Add to Dock" on some versions) → Add.
  - **Firefox, Edge**: behind the "···" menu → Share → "Add to Home Screen".
  Detection: iOS platform check (`/iP(hone|od|ad)/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)`) plus a UA browser-token switch (`CriOS` → Chrome, `FxiOS` → Firefox, `EdgiOS` → Edge, `DuckDuckGo` token → DuckDuckGo, none of those → Safari) to pick the matching copy/icon variant. Gate on `!window.navigator.standalone`.
  **Known exception**: EU users on iOS 17.4+ may be running a browser on an alternative (non-WebKit) engine under the DMA — Add-to-Home-Screen support for those specific builds is newer and less consistent; verify per-browser rather than assuming parity with the WebKit version of the same browser.
- **Update toast — position & stacking**: anchor at `bottom: calc(90px + env(safe-area-inset-bottom))` (90px = TabBar's own total height, already containing the FAB's upward protrusion) — NOT `bottom: 0`. `z-index: var(--z-toast)` (50, already reserved for this). Offline Banner stays `position: sticky; top: 0; z-index: var(--z-sticky)` (10) — opposite screen edges, no true stacking conflict between them.
- **Camera permission primer → real capture**: Add Item's upload is currently a mock tap-target with no camera call. Wire `<input type="file" accept="image/*" capture="environment">` or `getUserMedia`, gated behind the primer's "Continue" action.
- **Calendar permission primer → real OAuth**: "Connect Calendar" currently just flips a boolean. Wire actual Google Calendar OAuth/consent, gated behind the primer's "Continue to Google" action.
- **Persisted flags**: `wtw_install_dismissed_at` (timestamp, 14-day cooldown, stop after 2 dismissals), `wtw_camera_primed`, `wtw_calendar_primed` — none of these localStorage reads/writes exist yet.

## -1. Dev state-override panel — prototype tool only, must not ship
The dashed-border panel top-left (screen picker + state picker: default/loading/empty/empty-filtered/error/offline) forces every screen into states that have no real backend to trigger them (`devOverrideScreen`/`devOverrideState` in state, `devFor()` in `renderVals()`, and every `*ShowLoading`/`*ShowError`/`*ShowEmpty*` flag it feeds). Strip all of it — the panel markup, the two state fields, `handleDevScreenChange`/`handleDevStateChange`/`clearDevOverride`/`retryDev`, `DEV_SCREEN_MAP`/`DEV_STATE_OPTIONS`, and every `devFor(...)` call — before shipping, and replace the flags it drives with real ones wired to actual loading/error/empty conditions from a real data layer.

## 0. Offline behavior is display-only, no real queuing
The global offline Banner and per-action disabling (upload, submit, Log as worn) are wired to `navigator.onLine`/`online`/`offline` events, but nothing is queued for retry. Add-item's upload trigger is simply disabled while offline — the copy does NOT promise "we'll upload once you're back" because no Background Sync exists. If that promise is wanted, implement: a persisted local queue (IndexedDB) of pending uploads, a Background Sync registration (`sw.sync.register('upload-queue')`) that flushes the queue on reconnect, and UI feedback (queued count, per-item retry/failed state) — don't just re-enable the button on `online`.


## 0.5 Full RTL — deferred, but logical properties are already in place
Icon mirroring (back chevron), bidirectional numerals, and translated (Persian) copy are deferred — not built. What IS done, so a later `dir="rtl"` pass is mostly a flip of a switch rather than a rewrite: every directional physical CSS property (`text-align:left/right`, `margin-left/right`, `left:`/`right:` used for edge-docking) across `What to Wear.dc.html`, `BottomSheet.dc.html` and `Switch.dc.html` was converted to its logical equivalent (`text-align:start/end`, `margin-inline-start/end`, `inset-inline-start/end`). A dev-panel "Direction" control already sets `dir` on the root for spot-checking layout mirroring; full RTL still needs the icon-mirror CSS, digit/typeface choice and copy below before it's real.

Deliberately left physical (do not convert blindly later):
- The brand-mark dot position inside the logo glyph (boot screen, auth header, Recommend hero ×2) — logos don't mirror by convention.
- Every hit-area centering pseudo-element (`top:50%;left:50%;transform:translate(-50%,-50%)`, used on ~15 buttons/controls) — this pairs a position offset with a *physical* `transform`; CSS has no logical transform equivalent, so converting only the offset half would misplace the hit-area under real RTL.
- Chat-bubble tail corner radii (`border-radius:14px 14px 4px 14px` etc.) — logical per-corner properties (`border-start-start-radius` etc.) exist but weren't applied this pass.

Single root fix that resolves most of this for free: set a real `dir="rtl"` on the document root (driven by locale), and make sure all layout uses **logical** properties (`margin-inline-start/end`, `padding-inline-start/end`, `inset-inline-start/end`, `text-align:start/end`) instead of literal `left`/`right`. Flex/grid `flex-end`/`flex-start` already auto-mirror — no change needed there.

### Mirrors
- **Back chevron** (`IconButton icon="back"`) — directional, must flip. Implement via `[dir="rtl"] .icon-back svg { transform: scaleX(-1); }` or a distinct mirrored path.
- **TopHeader** back-button + title order — already flex-based with no literal left/right; auto-mirrors correctly once `dir="rtl"` is set. No correction needed.
- **Chat bubble alignment** (`align-self:flex-end/flex-start`) — already logical; auto-mirrors. No correction needed.
- **Progress bar fill** (Add-item review queue) — plain `width:%` on a block child with no absolute positioning; anchors to the container's inline-start edge by normal flow, so it already grows from the correct edge once `dir="rtl"` is set. No correction needed.
- **Nav rail/sidebar** fixed offset — must use `inset-inline-start:0`, not `left:0`, so it relocates to the right edge under RTL.
- **Text alignment** — any hardcoded `text-align:left` (found in `BottomSheet.dc.html` row buttons) must become `text-align:start`.

### Must NOT mirror
- **Logo / app mark** (the rounded-square-with-dot glyph, and `logo.svg`) — brand marks stay fixed orientation regardless of document direction, same convention as any logo in a localized product.
- **Settings gear, dots/ellipsis, heart/heartFilled, calendar, plus, close (X)** — symmetric or non-directional glyphs, no change.
- **History icon** (circular arrow + clock, "Chat history" entry point) — represents time, not spatial direction; per Material/HIG convention, clock/history icons do not mirror.
- **Filter icon** (descending horizontal lines) — symmetric, no change.
- Any future horizontal swipe gesture would need to reverse direction in RTL — none exist today (Closet/Outfits scroll is vertical only).

### Numerals
Persian UI convention is mixed in practice — many Persian tech products (Telegram, Instagram Farsi) keep Western digits for counts/dates/percentages rather than switching to Eastern Arabic-Indic numerals, for consistency with global timestamps and to avoid parsing ambiguity. Recommend keeping Western numerals as the default, but make it a locale token (not hardcoded) so it's a deliberate choice per market, not an oversight.

### Typeface
Instrument Sans has no Arabic/Persian glyph coverage. Load a Persian-supporting face (e.g. Vazirmatn) conditionally under `lang="fa"`/`dir="rtl"` — the current file hardcodes one Latin family inline everywhere, so this is a font-loading + fallback-stack addition, not a redesign.

*Tool note:* this prototyping tool can't express a live `dir="rtl"` toggle across a 2000-line inline-styled file without a systemic left/right → logical-property rewrite; the above is the precise map for that rewrite, not applied live here.

These behaviors can't be expressed in this prototyping tool (inline-styles-only, no real DOM event model for keyboard/media features). Each item below is a precise spec for a developer.

## 0.6 Account deletion and data export \u2014 deferred, not built
Settings' Account section only has an editable email field \u2014 there is no delete-account flow, no data-export flow, and no password-change control. Given the app stores user photos and body/style data, these are near-mandatory before shipping. Deferred spec for whoever picks this up:
- **Delete account**: a destructive action in Account (danger-styled, likely its own confirmation `BottomSheet` \u2014 tone `danger` row per \u00a73), requiring a typed confirmation or re-auth, that deletes the user record, all closet item photos/metadata, outfits, chat history, and revokes the Google Calendar OAuth grant.
- **Data export**: a \"Download your data\" action (Account section) that packages closet items, outfits, and chat history as a downloadable file (JSON or a zip with photos) \u2014 relevant for GDPR/CCPA-style portability requirements.
- **Password change**: Account currently exposes only email; a change-password control (current password + new password + confirm) is missing entirely, separate from the forgot-password flow (\u00a74).

## 0.7 Greeting is hardcoded, not time-of-day-based
The Recommend screen's greeting always renders the literal string `'Good afternoon'` (`greeting: 'Good afternoon'` in `renderVals()`) regardless of actual time \u2014 there is no morning/evening variant and no clock read anywhere. `design-system.md` \u00a79 specifies the intended real behavior (three strings, hour boundaries); implement `new Date().getHours()` (or the user's local timezone equivalent) to pick between them.

## 0.8 Outfit match scores are hardcoded, not from a real recommender
Every outfit's `scores` object (`weather`/`formality`/`style`/`similar`, each a 0\u20131 float) is hand-authored directly in the seed data and in `scenarios()`'s `mk()` calls \u2014 there is no real scoring model. The **float\u2192label mapping itself is real logic that should ship** (`scoreLabelFor`/`scoreBreakdownFor` in the logic class: average the sub-scores, threshold at 0.8/0.6 into "Great match"/"Good match"/"Might work" \u2014 see `design-system.md`'s Scores section for the exact table), but the floats it consumes are fake. Wire an actual scoring endpoint that returns the same shape (a flat `{ [dimension]: 0\u20131 }` object per outfit) and this mapping code needs no changes.

## 1. True `:focus-visible`, not bare `:focus`
Every interactive element currently applies `box-shadow: var(--shadow-focus-ring)` via a generic focus handler, which fires on mouse click focus too (should only show for keyboard/assistive nav).

**Required implementation:** replace the focus style hook with a real CSS rule:
```css
.control:focus { outline: none; }
.control:focus-visible {
  box-shadow: 0 0 0 var(--focus-ring-offset, 2px) var(--color-focus-ring);
}
```
Apply to every button/link/input currently carrying the ring (Button, IconButton, Chip, Switch, SegmentedControl, TabBar items, TopHeader pill, BottomSheet rows). Do not add `:focus` (non-`-visible`) box-shadow anywhere — mouse/touch activation should show no ring.

## 2. Switch semantics and keyboard support — RESOLVED
`Switch.dc.html` now ships `role="switch"`, `aria-checked`, `aria-disabled`, `tabIndex` (0, or -1 when disabled), and a keydown handler (Space/Enter toggle). Still blocked on item 1 above for a true focus-visible ring (currently uses the generic bare-`:focus` hook like every other control).

## 3. Skeleton pulse must respect reduced motion
Implemented today as a CSS `@keyframes` gated by `@media (prefers-reduced-motion: no-preference)`, so the animation only plays when the user has NOT requested reduced motion. Ship this exact pattern as-is in code (already correct, just confirm the media query survives your build's CSS pipeline/minifier — some CSS-in-JS setups strip unused-looking media blocks):
```css
@keyframes skeletonPulse { 0%, 100% { opacity: 0.55; } 50% { opacity: 1; } }
@media (prefers-reduced-motion: no-preference) {
  .skeleton { animation: skeletonPulse 320ms cubic-bezier(0.4,0,0.2,1) infinite; }
}
```
Base/reduced-motion state: `opacity: 0.7`, static, no animation — this must remain the fallback whether or not the media query is supported by the runtime.
