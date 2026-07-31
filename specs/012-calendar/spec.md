# Feature Specification: Calendar

**Feature Branch**: `012-calendar`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Feature 012: Calendar. A user connects Google Calendar, sees their
upcoming events, and picks one to style for — with that choice surfacing back on the Recommend
screen. Full requirements, states, copy, and constraints are in docs/handoffs/012-calendar.md
(read first) plus design/design-system.md §4/§6/Calendar screen anatomy/'Date & time formats',
design/known-gaps.md §-2, docs/design-decisions.md §12, and docs/handoffs/013-profile-settings.md
§7. Migration number is 0004. In scope: migration 0004 (calendar_connections + picked event
context, RLS per migration 0002's pattern), /calendar screen with disconnected/connected-with-
events/connected-empty/error states plus loading skeleton and offline handling, computed
relative-day event date labels, picking an event disables all rows and surfaces 'Styling for
{event} · Change' on /recommend (a minimal addition to the feature-001 stub, since feature 008
owns that screen), a permission primer gated by a persisted wtw_calendar_primed flag before the
real Google OAuth consent screen, and wiring both /calendar's connect button and Settings →
Connected accounts' Google Calendar row to the same connection state (013's branch is not yet
merged into rebuild, so build the calendar side and shared client logic; do not build a
duplicate Settings screen). OAuth uses PKCE with an app-route redirect (never provider-hosted),
matching design-decisions §12's auth flow decision. Out of scope: the styling chat itself (008),
the suggestion pager (009), making weather services interactive (stays a non-interactive 'Coming
soon' badge), closet/outfits/profile screens, any cloud Supabase project."

## Clarifications

### Session 2026-07-31

- Q: Which of the user's Google calendars should the event list read from — just their primary
  calendar, or every calendar they can access? → A: Primary calendar only, using the least-
  privilege `calendar.events.readonly` scope. No per-calendar grouping/filtering UI exists in
  the design system, so a single primary-calendar list matches what the screen actually renders.
- Q: How far ahead — or how many events — should the "upcoming events" list actually fetch? →
  A: Next 7 days, capped at 20 events. Matches the design's plain scrollable list with no
  pagination control, and keeps a single request fast.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect Google Calendar (Priority: P1)

A signed-in user with no calendar connected visits `/calendar`, sees an explanation of what
connecting does, and connects their Google account so their events can be used for styling.

**Why this priority**: Nothing else in this feature has any content without a connection —
every other story depends on this one succeeding first.

**Independent Test**: As a user with no calendar connection, visit `/calendar`, confirm the
disconnected card renders with the specified copy, tap "Connect Google Calendar", complete (or,
in an environment without a live OAuth client, attempt) the consent flow, and confirm a
completed connection is persisted and reflected back on `/calendar`.

**Acceptance Scenarios**:

1. **Given** a signed-in user with no calendar connection, **When** they open `/calendar`,
   **Then** they see the disconnected card: icon tile, "Connect your calendar" title,
   explanatory body, and a full-width "Connect Google Calendar" button.
2. **Given** a user who has never seen the calendar permission primer, **When** they tap
   "Connect Google Calendar", **Then** a primer card appears first, explaining what the
   connection is for, before any provider consent screen.
3. **Given** a user who has already seen the primer (a persisted flag is set), **When** they
   tap "Connect Google Calendar" again in a later session, **Then** the primer does not
   reappear and the flow goes straight to consent.
4. **Given** a user completes the Google consent flow successfully, **When** they return to the
   app, **Then** the connection is persisted server-side and `/calendar` now shows the
   connected state.
5. **Given** a user cancels or fails the consent flow partway, **When** they return to the app,
   **Then** they remain in the disconnected state with no partial or broken connection
   persisted.

---

### User Story 2 - See upcoming events and pick one to style for (Priority: P1)

A user with a connected calendar sees their upcoming events and picks one, so the outfit
recommendation can be grounded in a real occasion.

**Why this priority**: This is the feature's actual payoff — connecting a calendar with no way
to use its events would be a dead end.

**Independent Test**: As a user with a connected calendar and at least one upcoming event, open
`/calendar`, confirm the event list renders with computed date/time labels, pick a row, and
confirm all rows become disabled and the pick is available to `/recommend`.

**Acceptance Scenarios**:

1. **Given** a connected user with upcoming events, **When** they open `/calendar`, **Then**
   they see the hint caption followed by a stacked list of event rows, each showing the event
   title and a `{relative day, time} · {location}` meta line computed from the event's real
   timestamp — never a hardcoded string.
2. **Given** an event list is showing, **When** the user taps one row, **Then** that event
   becomes the picked event, every row in the list (including the picked one) renders disabled
   (`opacity: 0.5`, `cursor: not-allowed`), and no row is shown as "selected" or highlighted.
3. **Given** an event has already been picked, **When** the user navigates to `/recommend`,
   **Then** the context line reads "Styling for {event} · Change" instead of the unpicked
   prompt.
4. **Given** a connected user with a picked event, **When** they tap "Change" on `/recommend`,
   **Then** they return to `/calendar` able to pick a different event.

---

### User Story 3 - Empty and error calendars (Priority: P2)

A connected user whose calendar currently has no upcoming events, or whose calendar sync fails,
is told clearly what happened and given a way to proceed anyway.

**Why this priority**: Necessary for a connected calendar to never present a dead or ambiguous
screen, but only reachable after Stories 1-2 already work.

**Independent Test**: As a connected user with zero upcoming events, open `/calendar` and
confirm the empty-state copy and the "Style something" bypass button; simulate a sync failure
and confirm the error state and its retry action.

**Acceptance Scenarios**:

1. **Given** a connected user with no upcoming events, **When** they open `/calendar`, **Then**
   they see the empty-state body copy and a "Style something" button that goes directly to
   `/recommend`, bypassing the event list entirely.
2. **Given** a connected user whose calendar fails to sync (a real server-side failure, not an
   offline condition), **When** `/calendar` loads, **Then** they see the error-state copy and a
   retry action.
3. **Given** the client is offline, **When** `/calendar` would otherwise show its own error
   state, **Then** the screen suppresses that error and relies on the global offline banner
   instead, per the app's error-vs-offline precedence rule.

---

### User Story 4 - Disconnect from either entry point (Priority: P2)

A connected user disconnects Google Calendar from Settings → Connected accounts, and that
disconnection is immediately reflected on `/calendar` (and vice versa).

**Why this priority**: The two entry points sharing one source of truth is explicitly called
out as easy to get wrong; it is P2 because it depends on connect (P1) existing first, but it is
still core correctness, not a nice-to-have.

**Independent Test**: As a connected user, disconnect from one entry point and confirm the
other entry point (and any picked-event context) reflects disconnection without a page reload
being required to notice on next visit.

**Acceptance Scenarios**:

1. **Given** a connected user, **When** they disconnect from `/calendar`'s own affordance or
   from Settings → Connected accounts, **Then** the connection state updates server-side and
   both surfaces show "disconnected" the next time each is viewed.
2. **Given** a user disconnects while a picked event exists, **When** they next visit
   `/recommend`, **Then** the picked-event context is no longer shown (disconnecting clears any
   picked event, since it can no longer be verified against a live connection).

---

### Edge Cases

- What happens when a user's OAuth token expires between visits? The next request that needs it
  attempts a silent refresh; if refresh fails, the user is treated as disconnected and shown the
  disconnected state again rather than a broken connected one.
- What happens when the Google OAuth client credentials are not configured in a given
  environment? The "Connect Google Calendar" button remains visible and wired, exactly as
  feature 003 handles the equivalent Google sign-in gap — it is not hidden, stubbed, or faked
  into a false "Connected" state.
- What happens when a user picks an event, then that event is deleted or moved on the Google
  side before they reach `/recommend`? Out of scope for this slice — the picked context is a
  point-in-time snapshot (title, time, location) taken when picked; live re-validation against
  Google is not required.
- What happens when a user has more than 20 events in the next 7 days? The list is capped at 20
  (the earliest 20, by start time); no pagination or "load more" exists for this screen, per
  the design system.
- What happens if a second browser tab picks a different event while `/recommend` is open in
  another? Last write wins server-side; no real-time sync between tabs is required.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `/calendar` route rendering exactly one of: disconnected,
  connected-with-events, connected-empty, or error, plus its own loading (skeleton) state and
  participation in the global offline state.
- **FR-002**: System MUST show a permission primer, gated behind a persisted
  `wtw_calendar_primed` flag, before the real Google OAuth consent screen the first time a user
  attempts to connect; subsequent connect attempts MUST skip the primer once the flag is set.
- **FR-003**: System MUST perform the Google Calendar OAuth connection using PKCE, redirecting
  through an app-owned route rather than a provider-hosted page, with every redirect URL on the
  provider's allow-list.
- **FR-004**: System MUST persist a completed calendar connection server-side, scoped to the
  owning user, and MUST NOT persist a connection for a cancelled or failed OAuth attempt.
- **FR-005**: System MUST never store an OAuth access or refresh token in a tracked file, a log
  line, or any error response returned to the client.
- **FR-006**: System MUST render each upcoming event from the user's **primary Google
  calendar only**, within the **next 7 days and capped at 20 events**, as a row showing the
  event title and a computed `{relative day, time} · {location}` meta line, where the
  relative-day label is Today, Tomorrow, a weekday name for the next ~6 days, or a short date
  beyond that, derived from the event's actual timestamp — never a fixed string. When an event
  has no location, the meta line MUST show only `{relative day, time}` — the `· {location}`
  segment and its separator are omitted entirely, never rendered as a blank or placeholder
  value.
- **FR-007**: System MUST let a user pick exactly one event from the list; picking one MUST
  disable every row in the list (visually and to interaction) and MUST NOT render any row as
  "selected" or highlighted.
- **FR-008**: System MUST surface the picked event's context on `/recommend` as "Styling for
  {event} · Change" when an event is picked, and as a "Style for an event from calendar" link
  when none is picked.
- **FR-009**: System MUST let the user return to `/calendar` from `/recommend`'s "Change"
  action to pick a different event.
- **FR-010**: System MUST show a connected-empty state (with a "Style something" action that
  bypasses the calendar and goes directly to `/recommend`) when a connected user has zero
  events in the next 7 days, distinct from the disconnected state.
- **FR-011**: System MUST show an error state with a retry action when a connected user's
  calendar fails to sync for a real (non-offline) server-side reason, and MUST suppress that
  error state in favor of the global offline banner when the client itself is offline.
- **FR-012**: System MUST expose calendar connect/disconnect as a single shared piece of state
  reachable from two entry points — `/calendar`'s own affordance and Settings → Connected
  accounts' Google Calendar row — such that an action taken at either entry point is reflected
  at both.
- **FR-013**: System MUST clear any picked event when the calendar connection is disconnected,
  from either entry point.
- **FR-014**: System MUST enable row-level security on the calendar connection and picked-event
  data such that one user can never read or modify another user's calendar connection or picked
  event, and this isolation MUST be proven by a test that exercises the policy directly (not
  only through the application's own query-level filtering).
- **FR-015**: System MUST leave "Weather services" in Connected accounts as a non-interactive
  "Coming soon" badge; this feature MUST NOT make it interactive.
- **FR-016**: System MUST render all of `/calendar`'s specified states in both light and dark
  themes at 320/768/1024/1440px.
- **FR-017**: System MUST keep the Google Calendar connect option visible and fully wired even
  in an environment where the OAuth client credentials are not configured, consistent with how
  feature 003 handles the equivalent gap for Google sign-in — never hidden, stubbed, or faked
  into a false connected state. Unlike feature 003's Google sign-in button (which can be
  disabled ahead of the click via a live, unauthenticated GoTrue settings check), no equivalent
  live signal exists for this feature's own backend configuration, so the button MUST stay
  enabled unconditionally; the unconfigured case surfaces only when actually attempted, as a
  clear failure response distinct from a crash, never echoing any credential value.

### Key Entities

- **Calendar connection**: One user's link to their Google Calendar — whether connected, the
  provider tokens needed to fetch events (stored server-side only, never client-exposed), and
  when the connection was established. Exactly zero or one per user.
- **Picked event**: A snapshot (title, start time, location) of the single upcoming event a user
  has chosen to style for, captured at pick time. Exactly zero or one per user; cleared when the
  calendar connection is disconnected or when a new event is picked.
- **Calendar event (read-only, not persisted)**: An item fetched live from the connected Google
  Calendar for display in the event list — not stored by this system beyond what a picked event
  snapshots.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with a connected calendar and upcoming events can go from opening
  `/calendar` to a picked event visible on `/recommend` in three taps or fewer.
- **SC-002**: 100% of event rows shown display a relative-day label computed from the event's
  real timestamp; none render a hardcoded date string.
- **SC-003**: Disconnecting from either `/calendar` or Settings → Connected accounts is reflected
  at the other entry point 100% of the time, with no manual refresh required beyond a normal
  navigation to that screen.
- **SC-004**: A row-level-security isolation test demonstrates 0% cross-user visibility into
  calendar connection or picked-event data.
- **SC-005**: Every one of `/calendar`'s specified states is visually verifiable in both themes
  at 320/768/1024/1440px, with no missing or visually broken state.
- **SC-006**: No OAuth token appears in a tracked file, a log line, or a client-facing error
  response, verified by code review and by inspecting actual error payloads.

## Assumptions

- A Google Cloud OAuth client ID/secret may or may not be available in the environment this
  feature is built and verified in. Where it is not fully usable end-to-end, the connect flow is
  still fully built and wired — reported as untested for the live round-trip rather than
  removed, stubbed, or faked, per `docs/handoffs/012-calendar.md` §2. This is an explicit
  exception to "all acceptance scenarios verified": User Story 1's live consent round-trip may
  ship verified only against fixture data in some environments.
- Feature 013 (Settings) may not be merged into `rebuild` yet when this feature is built. Where
  that is the case, this feature builds its own side (the connection state, the backend
  endpoints, and shared client logic) and does not build a duplicate Settings screen; wiring
  Settings' existing inert row is left as a documented, trivial follow-up.
- "Local only" — this feature targets a local Supabase project. No cloud Supabase project is
  provisioned or targeted as part of this work.
- The event list reads live from Google Calendar on each `/calendar` visit rather than syncing
  and storing a copy — only the single picked event is persisted, per the Key Entities section.
- `/calendar`'s and `/recommend`'s visual content (layout, copy, tokens) is fully specified in
  `design/design-system.md` and `docs/design-decisions.md`; this spec does not restate that
  content, only the behavior it must satisfy.
- The styling chat, the outfit-suggestion pager, and every other part of `/recommend` beyond the
  calendar-context line are feature 008's scope, not this feature's — this feature's touch to
  `/recommend` is limited to the context line described in FR-008/FR-009.
