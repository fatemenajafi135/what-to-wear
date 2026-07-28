# Feature Specification: App shell, design tokens, component library, and PWA basics

**Feature Branch**: `001-app-shell`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "App shell, design tokens, component library, and PWA basics — the foundation slice for the What to Wear rebuild. Stand up the Next.js App Router application shell, the three-layer design-token pipeline (system → semantic → theme, light/dark, boot-time theme selection with no flash), the shared component library (Button, IconButton, Chip, Badge, Switch, SegmentedControl, TopHeader, TabBar, BottomSheet, AvatarInitial, Banner, Input, Textarea, Select, DatePicker, TagInput — each with its full state matrix in both themes), responsive CSS-only app chrome (bottom tab bar 0-767px, 76px icon rail 768-1023px, 240px sidebar 1024px+, identical routes at every tier), route stubs for /recommend, /closet, /outfits, /profile, /profile/settings, /add (each rendering only its chrome and empty state, no data, no auth), and PWA basics (manifest.ts, per-theme meta theme-color tags, safe-area insets, / redirect logic). No auth screens, no real data or API calls, no service worker/caching/install prompt (those are features 002 and 007). Full context and decisions already made are recorded in docs/handoffs/001-app-shell.md, design/design-system.md, and docs/design-decisions.md."

## Clarifications

### Session 2026-07-28

- Q: How should the sixteen shared components' full state matrices be verified during this slice — a dedicated component-catalog route, or ad hoc/code-review only? → A: Dev-only catalog route — a route excluded from primary navigation and from the production build's discoverable surface, rendering every component in every documented state in both themes side by side.
- Q: Should the boot-time theme choice be readable by the server at render time (cookie + SSR), or stay client-only (inline blocking script)? → A: Cookie + SSR — a persisted override is stored in a cookie; the server reads it (or a safe default when absent) and renders the correct `data-theme` directly in the initial HTML response, so no client-side script is required to avoid the flash.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consistent chrome at any device size (Priority: P1)

A person opens What to Wear on a phone, a tablet, and a desktop browser. At every size the same destinations are reachable (Recommend, Closet, Outfits, Profile) through chrome appropriate to that size — a bottom tab bar on a phone, an icon rail on a tablet, a labelled sidebar on desktop — and resizing the window between these sizes never breaks the layout or hides a destination.

**Why this priority**: Every other feature is built inside this chrome. If navigation doesn't hold at every breakpoint, no downstream screen can be verified either.

**Independent Test**: Load each stub route at 320px, 768px, 1024px and 1440px viewport widths and confirm the same four primary destinations are present and reachable, with only the chrome's presentation changing.

**Acceptance Scenarios**:

1. **Given** a viewport narrower than 768px, **When** the app loads, **Then** primary navigation renders as a bottom tab bar and the "Create" action renders as a floating circular button between Closet and Outfits.
2. **Given** a viewport between 768px and 1023px, **When** the app loads, **Then** primary navigation renders as a 76px icon-only rail with "Create" as a icon button pinned above a divider at the top of the rail.
3. **Given** a viewport of 1024px or wider, **When** the app loads, **Then** primary navigation renders as a 240px labelled sidebar with "Create" as a full-width labelled pill, and the Profile item shows the user's avatar-initial in place of its generic icon.
4. **Given** any of the three tiers, **When** a person navigates from one primary destination to another, **Then** focus moves to the new screen's heading and the previous screen's content is fully replaced.

---

### User Story 2 - Every shared component reads correctly in light and dark, in every state (Priority: P1)

A person (or a future feature relying on this component library) encounters a Button, Chip, Switch, Input, or any of the other shared components. Regardless of which theme is active (light or dark, chosen by system preference or a persisted override) and regardless of the component's state (default, hover, active, focus-visible, disabled, loading, error, or empty, where applicable), the component renders with correct, on-token visual treatment and correct accessibility semantics.

**Why this priority**: This is the foundation slice's core deliverable — every later feature composes screens out of these components. A component with an untested or wrong state is a bug that resurfaces on every screen that uses it.

**Independent Test**: Render each of the sixteen components (the eleven from the design system plus the five form controls) in the dedicated dev-only component-catalog route, cycle every documented state in both themes, and confirm no raw color or pixel value appears anywhere in the rendered output that doesn't trace back to a token.

**Acceptance Scenarios**:

1. **Given** the dark theme is active, **When** a disabled Button, Chip, or Switch is rendered, **Then** it shows at 50% opacity with pointer events disabled, using the same semantic tokens as its enabled state (no separate "disabled" color).
2. **Given** a person navigates using only a keyboard, **When** they tab to any interactive control, **Then** a visible focus ring appears; **when** they instead activate the same control with a mouse click, **then** no focus ring appears.
3. **Given** a BottomSheet is open, **When** a person presses Tab repeatedly, **Then** focus cycles only among the sheet's own focusable elements and never escapes to the page behind it; **when** the sheet closes, **then** focus returns to the control that opened it.
4. **Given** `prefers-reduced-motion: reduce` is set, **When** any of the shell's five animated transitions would normally play (skeleton pulse, Switch thumb-slide, boot logo pulse, BottomSheet open/close, pager slide), **Then** the transition is replaced by its static equivalent with no motion.

---

### User Story 3 - The app installs cleanly as a PWA and boots without a visual glitch (Priority: P2)

A person adds What to Wear to their home screen (or their browser recognizes it as installable) and later opens it in standalone mode. The app presents the correct name, icon, and background/theme color throughout the install and launch flow, and on every cold start — installed or in a browser tab — the correct theme (light or dark) is visible from the very first frame, with no flash of the wrong theme.

**Why this priority**: Installability is a concrete, testable gate (Lighthouse) that downstream PWA work (feature 007) builds on, but it is not required for a person to use the web experience today, so it ranks behind the two chrome/component stories.

**Independent Test**: Run a Lighthouse PWA-installability audit against the deployed stub app and confirm it passes; separately, force each theme via OS-level `prefers-color-scheme` and reload the app repeatedly, confirming the first painted frame always matches the expected theme.

**Acceptance Scenarios**:

1. **Given** a person's system preference is dark mode and they have never toggled an in-app override, **When** the app loads cold, **Then** the very first rendered frame uses the dark theme's tokens — no visible flash of the light theme.
2. **Given** a person has previously chosen a theme override in-app, **When** they reload, **Then** the persisted override wins over the system preference.
3. **Given** the app is installed and launched in standalone display mode on a device with a notch or home-indicator, **When** any screen renders its chrome, **Then** edge-docked elements (tab bar, sheets, toasts) clear the device's safe-area insets and are not obscured by system UI.
4. **Given** the app is loaded as a plain browser tab (not installed), **When** any screen renders its chrome, **Then** no extra safe-area padding is added beyond what the browser chrome already reserves.
5. **Given** a person navigates to `/`, **When** the app resolves the redirect, **Then** they land on `/recommend` (the authenticated default for this slice, since no real auth exists yet) rather than seeing a blank or 404 route.

---

### Edge Cases

- What happens when a person resizes the browser window across a breakpoint (e.g., 767px → 768px) while a BottomSheet or other overlay is open? The overlay must remain functional and must not strand focus outside its trap.
- How does the shell behave when a route stub (e.g., `/add`) is deep-linked directly with no navigation history (e.g., opened from a manifest shortcut)? Closing/dismissing it must land on a sensible fallback screen rather than erroring.
- What happens when `prefers-color-scheme` cannot be determined (unsupported browser)? The app must fall back to a defined default theme rather than rendering unstyled.
- How does a screen reader user experience a route that has no visible TopHeader (e.g., Profile)? A visually-hidden `<h1>` must still be present and receive focus on navigation.
- What happens to the "Create" action across breakpoints when a person navigates directly to `/add` — is it treated as a nav destination (it must not be, per scope) or an overlay launcher?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The application MUST render identical primary destinations (Recommend, Closet, Outfits, Profile) at every viewport width, changing only the chrome presentation (bottom tab bar below 768px, icon rail from 768–1023px, labelled sidebar from 1024px up) via CSS alone, with no client-side viewport detection required for the initial layout.
- **FR-002**: The application MUST provide stub routes for `/recommend`, `/closet`, `/outfits`, `/profile`, `/profile/settings`, and `/add`, each rendering its chrome and a defined empty state, with no real data, no data fetching, and no authentication gate.
- **FR-003**: The "Create" action MUST be presented as an overlay launcher (not a fifth navigation destination) whose position and shape vary per breakpoint (floating circular button on mobile, icon button on tablet, labelled pill on desktop), per the source design's nav-mapping.
- **FR-004**: The application MUST implement a three-layer token pipeline — theme-independent system tokens, semantic tokens, and light/dark theme blocks — such that no component in the shared library or the route stubs references a raw color, spacing, radius, or font-size value directly.
- **FR-005**: The application MUST select the active theme (light or dark) at the server, before any HTML is sent to the browser: a persisted user override (stored so the server can read it, e.g. a cookie) takes precedence when present, otherwise the system's color-scheme preference is used, so that no visibly wrong theme is ever painted on cold start and no client-side script is required to prevent the flash.
- **FR-005a**: The application MUST provide a dev-only component-catalog route, excluded from primary navigation and from the production build's discoverable surface, that renders every one of the sixteen shared components in every state of its documented matrix, in both themes, so the component-library definition-of-done item is mechanically checkable rather than verified ad hoc.
- **FR-006**: The shared component library MUST include all sixteen components (Button, IconButton, Chip, Badge, Switch, SegmentedControl, TopHeader, TabBar, BottomSheet, AvatarInitial, Banner, Input, Textarea, Select, DatePicker, TagInput), each implementing its full documented state matrix (at minimum: default, hover on pointer devices, active, focus-visible, disabled; plus loading/error/empty where specified) in both themes.
- **FR-007**: Every interactive control smaller than 44×44px in either dimension MUST expose a 44×44px minimum tap/click target without enlarging its visible paint.
- **FR-008**: Every interactive control MUST show its focus indicator only on keyboard/assistive-technology focus (`:focus-visible`), never on mouse or touch activation.
- **FR-009**: Every screen MUST expose exactly one `<h1>` (visually hidden where no visible header exists), and focus MUST move to that heading whenever the person navigates to a new screen.
- **FR-010**: The BottomSheet component MUST implement real dialog semantics: it is announced as a modal dialog, traps keyboard focus among its own contents while open, and restores focus to the control that opened it when it closes.
- **FR-011**: Every animation the shell introduces (skeleton pulse, Switch thumb-slide, boot/splash logo pulse, BottomSheet open/close, and the outfit-pager slide, wherever their host component exists in this slice) MUST be skipped in favor of an instant, static equivalent when the person has requested reduced motion.
- **FR-012**: The application MUST declare a web app manifest with the app's name, icons, display mode, colors, and two shortcuts pointing at the real `/add` and `/recommend` routes.
- **FR-013**: The application MUST present the correct status-bar-adjacent color for the active theme via both light and dark `theme-color` meta tags, independent of the manifest's single static color.
- **FR-014**: Every fixed or sticky element docked to a device edge MUST resolve its offset through the platform's safe-area inset mechanism rather than a hardcoded pixel guess, and MUST NOT add extra padding when running in a plain browser tab where the browser chrome already occupies that space.
- **FR-015**: Navigating to `/` MUST redirect to `/recommend`, since this slice has no real authentication and treats every visitor as signed in for stub purposes; the signed-out redirect target (`/signin`) is out of scope until feature 002 exists.
- **FR-016**: The application MUST NOT include any code, markup, or dev-only affordance from `design/prototype/`, and in particular MUST NOT include anything under `design/prototype/_scaffolding/` (the device-bezel frame, viewport/direction dev selectors, dev state-override panel, or floating theme toggle).
- **FR-017**: The application MUST NOT implement authentication screens, real data fetching, a service worker, caching, or an install prompt — these are explicitly reserved for later features.
- **FR-018**: The application MUST render a boot/splash pre-hydration state — a centered brand mark on the background token, the wordmark in the Display type style — whenever a route segment is loading, with its pulse animation gated by reduced-motion per FR-011; this state belongs to this slice per `docs/design-decisions.md` §10, even though it is not a routable screen.

### Key Entities

This slice introduces no persisted data entities — it is chrome, tokens, and stub screens only. The only stateful concepts are:

- **Theme preference**: light or dark, resolved from system preference at boot and overridable by a persisted person-level choice; no server-side representation in this slice.
- **Navigation destination**: one of the four primary routes plus their sub-routes; identical across breakpoints, differing only in how their chrome is presented.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The same four primary destinations are reachable, and the layout holds with no visual breakage, at all four reference viewport widths (320px, 768px, 1024px, 1440px).
- **SC-002**: 100% of the sixteen shared components render every state in their documented matrix correctly in both light and dark themes, with zero raw hex or magic pixel values found in component code.
- **SC-003**: A keyboard-only pass reaches every interactive control in the shell and every stub screen, with a focus ring visible on keyboard navigation and absent on mouse activation, in 100% of controls checked.
- **SC-004**: A Lighthouse PWA-installability audit against the built app passes with no installability errors.
- **SC-005**: Across 20 repeated cold loads split evenly between forced light and forced dark system preference, 0 show a visible flash of the wrong theme.
- **SC-006**: On a real notched device in installed standalone mode, every edge-docked element clears the device's safe-area insets with no visual overlap with system UI, verified by manual device check.

## Assumptions

- No real authentication exists yet, so `/` always redirects to `/recommend` in this slice; the signed-out branch to `/signin` is deferred to feature 002 and is not testable until then.
- "Empty state" for each route stub means the screen's defined empty-state copy and layout from `design/design-system.md` §6, not a blank page — no live data source backs it in this slice.
- The four reference viewport widths (320, 768, 1024, 1440) are treated as the acceptance boundary set for responsive behavior, matching the handoff's definition of done.
- Where the design system and `docs/design-decisions.md` disagree, `docs/design-decisions.md` wins, per that document's own stated precedence and the handoff brief.
- The boot/splash state (FR-018) is not a route or a screen in the screen graph — it is the
  shell's own pre-hydration/route-loading state, per `docs/design-decisions.md` §10.
- The outfit-suggestion pager, its motion, and its host screen are out of scope for this slice (they belong to the styling feature); the reduced-motion requirement (FR-011) applies to it only insofar as its host component ships in this slice, which it does not — it is listed for completeness against the design system's animation inventory but has no acceptance test here.
