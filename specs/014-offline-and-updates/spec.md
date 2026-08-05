# Feature Specification: Offline, caching and the update prompt

**Feature Branch**: `feat/014-offline-and-updates`

**Created**: 2026-08-05

**Status**: Draft

**Input**: User description: "Offline, caching and the update prompt (feature 014). Full brief: docs/handoffs/014-offline-and-updates.md. Mission: the app keeps working when the network doesn't, and tells the user when a new version is ready. Today there is no service worker at all in frontend/ — Serwist is not installed, every asset and request goes to the network every time. This slice must: (1) wire Serwist into the Next build with a deliberate cache strategy per route class, with authenticated/user-scoped responses purged on sign-out, and signed photo URLs handled so an expired cached response never renders a broken image; (2) precache the app shell so a cold start with the network off renders the app's own chrome rather than the browser's offline error page; (3) detect a waiting/updated service worker and show an update-prompt toast that reloads into the new version on accept. Out of scope: offline queueing/Background Sync, beforeinstallprompt/iOS install card/permission primers/splash (feature 015), push notifications, any backend change, any change to pipeline/scoring/retrieval. Do not rebuild feature 001's manifest, theme-color, safe-area, or offline-banner work — only extend it."

## Clarifications

### Session 2026-08-05

- Q: How should the app detect that a new version is available while a client is already open, without the user closing and reopening it? → A: Reload-triggered only — detection happens on the client's next natural full navigation/reload (browser back-navigation, opening the installed app again, an explicit refresh), not via foreground polling or a visibility-change listener. No JS-side interval or `visibilitychange` check is added.
- Q: If the user dismisses the update toast without accepting, should it reappear later, or stay dismissed? → A: Stays dismissed until the next reload/relaunch. Consistent with reload-triggered detection — there is no other event during the same page session that would justify re-showing it, since in-app (client-side) navigation never re-checks the service worker.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Opening the app with no network shows the app, not a browser error (Priority: P1)

A returning user has the app installed (or has previously visited it) and opens it while their device has no network connectivity — a subway platform, a dead spot, airplane mode. Today this shows the browser's own "no internet" error page. Instead, the app's own chrome (navigation, header, static shell) must render, with the already-visible offline banner communicating the lack of connectivity, rather than a blank browser error.

**Why this priority**: This is the mission statement's first half, and the precondition for every other offline behavior — a browser error page pre-empts everything else in this spec.

**Independent Test**: With the app previously loaded once, turn off the network (airplane mode or DevTools "Offline"), force a full reload (not just an in-app navigation) at any route, and confirm the app shell renders — header, tab bar, and the existing offline banner — instead of the browser's offline interstitial.

**Acceptance Scenarios**:

1. **Given** the user has loaded the app at least once while online, **When** they go fully offline and reload the page, **Then** the app shell (navigation chrome, static layout) renders, and the existing offline banner is visible.
2. **Given** the user is offline and mid-session data (closet items, outfits, etc.) was already fetched this session, **When** they navigate between screens they've already visited, **Then** previously-seen data for those screens is still visible rather than a blank/error state, clearly distinguished from live data (the offline banner stays visible throughout).
3. **Given** the user is offline and requests a screen or a photo they have never fetched before, **When** the fetch fails, **Then** the screen's normal empty/error affordance appears — never a raw browser network error — and no copy implies the missing data will appear automatically once reconnected.

---

### User Story 2 - Signing out leaves no trace of the previous user's cached data (Priority: P1)

Two people share a device (or a user signs out at a public kiosk-like scenario). After user A signs out and user B signs in, nothing belonging to user A — their closet photos, outfit history, chat sessions — is visible or recoverable from the app's local cache, even offline.

**Why this priority**: Named as a hard privacy constraint in the brief — a cache that survives sign-out is described as "a real privacy problem, not a staleness annoyance." Equal priority to User Story 1 because shipping caching without this is actively unsafe, not merely incomplete.

**Independent Test**: Sign in as user A, browse the closet/outfits/chat history so their data populates the cache, sign out, sign in as user B on the same device/browser profile, and confirm (via DevTools' Application → Cache Storage panel and by going offline) that nothing of user A's is retrievable.

**Acceptance Scenarios**:

1. **Given** user A has browsed screens that fetched their personal data, **When** user A signs out, **Then** all caches holding that user-scoped data are cleared before the sign-in screen is usable.
2. **Given** user A has signed out and user B signs in on the same device, **When** user B goes offline and revisits screens user A had cached, **Then** none of user A's data appears — user B sees only their own previously-fetched data, or an empty/offline state if they have none cached yet.
3. **Given** a signed-out (unauthenticated) visitor, **When** they load the app offline, **Then** no authenticated user's data is ever exposed on the sign-in screen or any pre-auth route.

---

### User Story 3 - A signed photo URL that has expired never renders as a broken image (Priority: P2)

Wardrobe item photos are served through time-limited signed URLs. A user who returns to a screen after the signing window has passed (an hour) — including while offline, where a fresh URL cannot be fetched — must never see a broken-image icon in a spot where a photo previously loaded.

**Why this priority**: Named explicitly in the brief as a hard case with two different failure modes depending on what gets cached (the API response vs. the image bytes). It's a visible correctness bug if unhandled, but scoped to one visual element rather than a whole screen, so it ranks below the two above.

**Independent Test**: Load a screen with item photos, wait past the signed-URL expiry window (or simulate it), reload without a network round-trip able to mint a fresh URL (e.g., offline), and confirm the photo tile shows the app's existing no-photo/placeholder treatment rather than a broken-image glyph.

**Acceptance Scenarios**:

1. **Given** a photo was viewed and its signed URL has since expired, **When** the user revisits that screen offline (no way to mint a new signed URL), **Then** the tile shows the app's existing placeholder/no-photo treatment, never a broken-image icon.
2. **Given** the user is back online and revisits a screen with an expired photo reference, **When** the screen re-fetches, **Then** a freshly-signed URL is used and the real photo renders normally.

---

### User Story 4 - The user is told when a new version of the app is ready, and can get it with one tap (Priority: P1)

The team ships a fix or a new feature. A user who already has the app open, or has it installed, is currently stuck on the old version indefinitely (nothing tells them to refresh, and simply reloading may keep re-serving the old cached version). This story makes an already-installed/open client detect the new version and offer to switch to it.

**Why this priority**: The brief calls this "the single highest-risk thing in the slice" — a stuck service worker is sticky and can outlive the fix meant to replace it, which is a shipping-safety concern, not just a UX nicety. Equal priority to the P1 stories above.

**Independent Test**: Ship a change (a new build), then perform a full reload/relaunch of an already-installed client (not just in-app navigation) and confirm a toast appears offering the update; tapping it reloads the client onto the new version, verifiable by a visible marker of the new build being present afterward.

**Acceptance Scenarios**:

1. **Given** a client has the app open with an older version active, **When** the user performs their next full page reload or relaunch (browser back-navigation to a fresh document load, reopening the installed app, an explicit refresh — not an in-app client-side route change) and a new version has been deployed, **Then** the browser's own service-worker update check runs on that reload, the new worker installs and enters the waiting state, and an update-available toast appears without any further action from the user.
2. **Given** the update toast is visible, **When** the user taps its accept action, **Then** the app reloads and the new version's code is what actually runs afterward (not just a page refresh that re-serves the stale cached version).
3. **Given** the update toast is visible, **When** the user dismisses it or ignores it, **Then** the app keeps working normally on the current version for the rest of that session, and does not force the reload or re-show the toast until the next reload/relaunch.
4. **Given** `prefers-reduced-motion` is set, **When** the toast appears or is dismissed, **Then** it does so without the slide/fade motion, per the app's existing reduced-motion convention.

---

### Edge Cases

- What happens when the network drops mid-request (not before it)? The in-flight request fails; the screen must treat this the same as any other network failure it already handles (offline banner takes precedence over a screen's own error copy, per existing `design-system.md` §6 rule) — no new failure mode to design here, just confirm the service worker doesn't swallow or hang the failure.
- What happens to `POST /recommend/messages` (the billed styling chat call) if the user is offline or the request fails mid-flight? It must never be cached, queued, or automatically retried — a repeated call is a second billed LLM invocation. The send action's existing disabled-while-offline treatment is the entire offline behavior for this endpoint.
- What happens when the update toast is showing and the user is also offline? Both can be true at once (a stale service worker can be detected without any live network for other data). The toast and the offline banner occupy different screen edges (§3.2 of the handoff) and must not visually collide; the update itself only actually completes once the user is back online (the new assets have to be fetched), so accepting while offline should not silently fail without feedback.
- What happens if two tabs of the app are open when an update lands? Out of scope to solve cross-tab coordination beyond what the browser's own service worker lifecycle already provides; each tab independently detects and prompts.
- What happens the very first time a brand-new user visits (nothing cached yet) and they're offline? There is nothing to precache yet — this is a pre-existing, unavoidable case (you cannot use software you have never downloaded), not a regression this feature introduces. The browser's offline error page in this one case is acceptable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The app MUST register a service worker that precaches the application shell (static chrome: layout, navigation, core styles/scripts) so that a full-page load with no network available renders the app's own interface rather than the browser's offline error page, for any user who has loaded the app at least once before.
- **FR-002**: The app MUST apply a deliberate, documented caching strategy to each class of network request it makes (static assets, authenticated user-data reads, the billed styling-chat write, signed photo URLs), with the reasoning for each recorded — a uniform strategy applied without justification does not satisfy this requirement.
- **FR-003**: The app MUST NOT cache or automatically retry the billed styling-chat request under any circumstance (offline, failure, or otherwise).
- **FR-004**: The app MUST purge every cache that could contain authenticated, user-scoped data at sign-out, before the next sign-in can populate the cache with a different user's data.
- **FR-005**: The app MUST ensure a photo reference whose signed URL has expired, and which cannot be re-signed (e.g. because the client is offline), renders the app's existing no-photo/placeholder treatment rather than a broken-image icon.
- **FR-006**: The app MUST detect when a new version of the service worker/app is available on the client's next full page reload or relaunch (a real network navigation to the document), relying on the browser's own service-worker update check rather than an app-added foreground poll or visibility-change listener — an already-open tab that is never reloaded is not required to detect an update mid-session.
- **FR-007**: The app MUST show a visible, dismissible prompt when a new version is available, and MUST apply the new version only after the user explicitly accepts — it must never force a reload the user didn't ask for. Once dismissed, the prompt MUST NOT reappear until the next reload/relaunch.
- **FR-008**: Accepting the update prompt MUST result in the new version's code actually running afterward, not merely a page refresh that re-serves the previous cached version.
- **FR-009**: The update prompt's visual placement, stacking, and motion MUST follow the existing design-system conventions for toasts (positioned clear of the tab bar and safe-area insets, at the app's reserved toast layer, sliding/fading in and out) and MUST respect `prefers-reduced-motion`.
- **FR-010**: The update prompt's copy MUST come from a single, clearly-flagged source that the design owner can review and approve, not be invented ad hoc in component code (per the project's design-system-is-source-of-truth rule) — see the Assumptions section for how this is handled pending that review.
- **FR-011**: No copy anywhere in this feature may state or imply that an offline action is queued, saved for later, or will be automatically retried/synced once reconnected — no such mechanism exists or is in scope.
- **FR-012**: While offline, a screen MUST NOT show its own request-failure error copy for a failure that is simply the absence of network — the existing global offline banner is the single source of that messaging (existing rule, extended to any new failure path this feature introduces).
- **FR-013**: The offline/caching behavior described above MUST work identically whether the app is running in an ordinary browser tab or as an installed standalone PWA (per the project's one-codebase-serves-both-form-factors rule) — this feature introduces no separate code path per form factor.

### Key Entities

- **Service worker cache(s)**: Local, per-origin storage of previously-fetched responses/assets, scoped by request type (app shell, user data, images). Not user-facing data itself, but the mechanism that makes Stories 1–3 possible, and the thing Story 2 requires be provably emptied at sign-out.
- **Update prompt / toast**: A transient UI element representing "a newer version of the app exists," carrying an accept action (apply the update) and a dismiss path (keep using the current version).
- **Signed photo URL**: An existing, time-limited reference to a wardrobe item's photo, minted by the backend and already embedded in existing API responses (feature 006) — this feature does not change how it's issued, only how the client's cache must treat its expiry.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who has opened the app at least once, and later opens it again with zero network connectivity, sees the app's own interface within the same time it would normally take to load the shell online — not a browser network-error page — in 100% of observed cases.
- **SC-002**: After any sign-out, inspecting the device's local cache for the app shows zero entries containing the signed-out user's data, verified by direct inspection (not by inference from the UI alone).
- **SC-003**: Zero broken-image icons appear anywhere in the app as a result of an expired photo reference, across both the online and fully-offline conditions.
- **SC-004**: Within one reload/relaunch after a new version is deployed, 100% of already-open or already-installed clients that make any network-touching request are shown the update prompt (not silently stuck on the old version indefinitely).
- **SC-005**: Accepting the update prompt results in the newly-deployed version running, verifiable by an observable marker of the new build, every time it is tested.
- **SC-006**: No user-visible copy anywhere in the feature promises retry/queueing behavior that isn't implemented — zero instances found on review of every string this feature introduces.

## Assumptions

- The update-prompt's exact wording has no existing entry in the design system's copy tables (confirmed against `design-system.md` §6/§9). Per Principle VIII (the design system is the source of visual truth, including copy) and the precedent set in `docs/design-decisions.md` §51, this spec assumes a draft line will be written, kept in exactly one place, clearly flagged as a draft pending the design owner's review, and swapped for their answer once given — not treated as final copy invented in code.
- "The app" in every user story means the single Next.js codebase serving both the desktop web experience and the installed mobile PWA (Constitution IX) — no behavior described here is browser-tab-only or installed-only unless a story says so explicitly.
- Existing pre-001 groundwork (manifest, per-mode theme-color, safe-area insets, the offline banner and `navigator.onLine` wiring) is assumed present and unchanged; this feature only adds the service worker, its cache strategy, and the update prompt.
- Offline queueing/Background Sync, install prompts (`beforeinstallprompt`), the iOS manual-install card, permission primers, and push notifications are explicitly out of scope for this feature and are tracked elsewhere (feature 015, `docs/deferred-work.md` #7).
- "Cache cleared at sign-out" is scoped to caches this feature controls (the service worker's Cache Storage entries for user-scoped API responses and photos). It does not cover browser state outside this feature's control (e.g. the auth session mechanism itself), which is handled by existing sign-out code.
- Backend and AI pipeline behavior are unchanged; this is a client-only feature (Constitution I, no changes to `pipeline/`, `scoring/`, `retrieval/`).
