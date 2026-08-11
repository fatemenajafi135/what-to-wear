# Feature Specification: Calendar Pick Reaches Recommend

**Feature Branch**: `feat/020-calendar-pick-to-recommend`

**Created**: 2026-08-11

**Status**: Draft

**Input**: User description: GitHub issue #41 — "Calendar event pick dead-ends, and the pick
never reaches the conversation." Three linked defects: (1) picking an event on the Calendar
screen dims every row and saves the pick, but never navigates anywhere — the only way out is
the back button — and the save's own result is discarded, so a failed save looks identical to
a successful one; (2) the picked-event label on Recommend is fetched once on mount and can
read minutes stale because Next's Router Cache serves `/recommend` without remounting on
in-app navigation; (3) the picked event never reaches the styling conversation at all —
`recommend.py` never reads it, so picking an event today changes a label and nothing else.

## Clarifications

### Session 2026-08-11

This feature ran as a single unattended pass (no human available mid-flow to answer
`/speckit-clarify` questions). Every question below was resolved by the implementer using
the codebase's existing precedent, `.specify/memory/constitution.md`, and
`docs/design-decisions.md` as the sources of truth, and is recorded here rather than left
open, per that session's operating instructions.

- Q: Does the picked event seed a first assistant message, silently pre-fill every slot, or
  open with something the user must confirm? → A: Neither of the first two, and "confirm"
  only in a specific sense — see `docs/design-decisions.md` §61 for the full reasoning.
  Location (a reliable fact from the user's own calendar) is silently seeded into the
  conversation's slot state, the same channel every other extracted slot already uses.
  Occasion/formality (an inference from a free-text title, per Constitution IV not
  presentable as fact) is never silently asserted; the event's title and time are offered
  back as editable, unsent Composer text, requiring an explicit Send before they reach the
  pipeline at all. No new assistant-authored chat bubble is introduced — `design-system.md`
  fully specifies the hero's one welcome bubble, and §51 already draws the line for when
  something other than a human-authored string may appear as assistant copy.
- Q: What happens when the user's own words contradict the picked event (e.g. types a
  different location)? → A: The user always wins, via the mechanism that already exists for
  correcting anything said earlier in the conversation — a later turn's extraction overwrites
  the same graph-state `location` key the calendar seed wrote, with no special-cased
  precedence logic distinguishing a calendar-sourced value from a user-stated one.
  See §61.
- Q: Does the picked-event context on Recommend need the same persistence mechanism feature
  019 built (`recommendChatStore.ts`, a module-level store read via
  `useSyncExternalStore`, designed to survive a component unmount)? → A: The same *category*
  of fix (escape React's per-component mount lifecycle via a module-level store), but not the
  same *mechanism*. 019's bug was that real, generated conversation state was lost on
  unmount — the fix was to persist it outside the component tree. This defect's bug is that a
  value which must always reflect another screen's current server state (the picked event) was
  fetched once on mount and never refreshed. The fix here is a **write-through** module-level
  store: `handlePick`'s successful `PUT` response (defect 1's own now-checked result) is
  written directly into the store the instant it's confirmed saved, and `RecommendCalendarContext`
  subscribes to it via `useSyncExternalStore` instead of running its own mount-scoped fetch.
  This kills the staleness at its root — the UI updates the moment the write happens, with no
  dependency on whether the component holding it happens to remount — rather than trying to
  force a remount or a refetch to occur reliably, which is the same underlying lesson 019
  encodes (component-local, mount-tied state is the wrong home for anything that must reflect
  truth across an in-app navigation the Router Cache does not remount for) applied to a
  differently-shaped problem.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Picking an event takes you to Recommend (Priority: P1)

A user on the Calendar screen taps an upcoming event to style for. The save succeeds, and
they land on Recommend immediately — not after a wait, not by tapping back and finding it
already worked, and never by hitting a dead end they have to escape with the back button.

**Why this priority**: This is the literal bug report — picking an event currently strands
the user on Calendar. Nothing else in this feature matters if this doesn't work.

**Independent Test**: Connect a calendar with at least one upcoming event, tap it, and
confirm the app navigates to `/recommend` once the save completes, with no manual
navigation required.

**Acceptance Scenarios**:

1. **Given** the Calendar screen showing at least one upcoming event, **When** the user taps
   an event and the save succeeds, **Then** the app navigates to `/recommend`.
2. **Given** the same tap, **When** the save request fails (network error or non-2xx
   response), **Then** the user is NOT navigated away, the tapped row (and every other row)
   remains enabled/tappable — no row is left permanently disabled for a pick that was never
   actually saved — and a visible, actionable error is shown.
3. **Given** a save is in flight, **When** the user looks at the row list, **Then** rows are
   disabled for the duration of that one request (preventing a duplicate tap) without yet
   claiming an event has been picked — that claim (and the row-disabling `design-system.md`
   §"Connected, has events" specifies for a *confirmed* pick) is made only once the save
   response actually confirms it.

---

### User Story 2 - The Recommend screen always shows the current pick (Priority: P1)

A user picks an event on Calendar, lands on Recommend (User Story 1), and sees "Styling for
{event} · Change" immediately — not the stale "Style for an event from calendar" prompt, and
not a label that updates only after several more navigations or several minutes.

**Why this priority**: Equal priority to User Story 1 — landing on Recommend only to see
stale or absent context reproduces the same user-facing confusion the dead-end did, just one
screen later.

**Independent Test**: Pick an event, and without any additional wait, confirm the label on
Recommend already reads "Styling for {event} · Change." Then navigate to another tab and
back — the label stays current, not re-fetched-and-briefly-empty.

**Acceptance Scenarios**:

1. **Given** a user has just picked an event and been navigated to Recommend (User Story 1),
   **When** the Recommend screen renders, **Then** the calendar-context line already reads
   "Styling for {event} · Change," with no stale "Style for an event from calendar" flash.
2. **Given** a picked-event label is showing on Recommend, **When** the user navigates to
   another primary destination and back to Recommend, **Then** the label is still current —
   unaffected by whether the underlying page component happened to remount.
3. **Given** no event has ever been picked, **When** the user visits Recommend, **Then** the
   label reads "Style for an event from calendar," unchanged from today.

---

### User Story 3 - The stylist already knows what the calendar knows (Priority: P1)

A user picks an event, lands on Recommend, and starts a fresh conversation. The stylist does
not ask about things the calendar already answered reliably (location), and offers the
event's own details back to the user as an easy, editable starting point rather than
guessing at the occasion on their behalf.

**Why this priority**: This is the "desired" outcome the GitHub issue names directly — without
it, defects 1 and 2 only fix navigation and staleness; the pick still has no effect on what
gets styled.

**Independent Test**: With an event picked and a fresh (no prior messages) Recommend
conversation, confirm the Composer already contains editable text built from the event
(title + time), and that after sending it (edited or as-is) and asking "what should I wear,"
the stylist does not ask for the location again if the event carried one — while still asking
about anything the event didn't answer (e.g. mood, or occasion formality if the user's message
didn't make it clear).

**Acceptance Scenarios**:

1. **Given** a picked event with a `location`, and a fresh Recommend conversation, **When**
   the user sends their first message, **Then** the conversational reply does not ask for the
   location.
2. **Given** the same setup, **When** the user taps "Start styling" without ever mentioning a
   location themselves, **Then** the event's location still reaches weather-aware context
   assembly (i.e. the same `location` the picked event carries is what
   `assemble_context` receives).
3. **Given** a fresh Recommend conversation with a picked event, **When** the screen renders,
   **Then** the Composer's input is pre-filled with editable text derived from the event's
   title and time, and nothing about the event has been sent to the backend yet.
4. **Given** the pre-filled Composer text, **When** the user edits it before sending (e.g.
   changes the implied occasion) or types a different location later in the conversation,
   **Then** what the user sent is what the conversation and styling pipeline honor — the
   event never overrides a later, contradicting user statement.
5. **Given** a Recommend conversation that already has at least one user message, **When** the
   user picks a *different* event on Calendar and returns, **Then** the already-in-progress
   conversation's accumulated slots are left alone — only the calendar-context label updates
   (User Story 2); the mid-conversation state is not silently rewritten.

---

### Edge Cases

- What happens if the user picks an event, the save succeeds, but the subsequent navigation
  to `/recommend` is somehow interrupted (e.g. the user is offline right after)? → Out of
  scope beyond standard client-side navigation semantics; this feature does not add offline
  handling beyond what `useOnlineStatus` already provides elsewhere on this screen.
- What happens if a user with no picked event visits `/recommend` directly (never having
  been to Calendar)? → Unchanged: "Style for an event from calendar" prompt, no Composer
  pre-fill, identical to today's behavior.
- What happens on a *second* fresh conversation (after "New chat") when a previously-picked
  event is still on record? → The Composer is pre-filled again and `location` is re-seeded on
  the new thread's first turn — "fresh" is evaluated per-thread (no user messages / no
  `thread_id`), not per-event; the event stays "picked" until the user picks another one or
  disconnects the calendar (unchanged from today).
- What happens to the "way to change/clear" a picked event? → Unchanged and out of scope:
  the existing "Styling for {event} · Change" link already routes to `/calendar`; no new
  unpick affordance is introduced (see `docs/design-decisions.md` §61's explicit scope
  boundary).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST navigate the user to `/recommend` once — and only once — a
  calendar event pick has actually been confirmed saved by the backend.
- **FR-002**: The system MUST NOT mark an event as picked (disabled rows, "Styling for
  {event}" label) based on anything other than a confirmed-successful save response.
- **FR-003**: A failed pick save MUST leave the Calendar screen's rows usable again (no
  permanently disabled row for a pick that didn't take) and MUST show the user a visible,
  actionable error.
- **FR-004**: The Recommend screen's picked-event context MUST reflect the true current
  server state at the moment the user arrives there, whether that arrival follows immediately
  from a successful pick or from any other in-app navigation, without depending on whether the
  underlying page component happens to remount.
- **FR-005**: When a Recommend conversation is fresh (no prior user messages, no active
  thread) and a picked event exists, the conversation's `location` slot MUST be populated
  from that event before the first conversational reply is generated, without an LLM call
  being the mechanism that determines it.
- **FR-006**: The conversational reply generated for the first turn of such a thread MUST NOT
  ask the user for a location the picked event already supplied.
- **FR-007**: Starting a styling request ("Start styling") on such a thread, even before the
  location comes up explicitly in conversation, MUST still carry the picked event's location
  into context assembly.
- **FR-008**: The system MUST NOT derive or assert an occasion or formality value from the
  picked event's title and present it to the styling pipeline as a stated fact.
- **FR-009**: When a Recommend conversation is fresh and a picked event exists, the Composer
  MUST be pre-filled with editable text derived from the event's title and time; this text
  MUST NOT be sent to the backend until the user takes an explicit send action.
- **FR-010**: A later, contradicting user statement (in the pre-filled text once edited, or in
  any subsequent message) MUST take precedence over anything seeded from the picked event, via
  the same extraction/overwrite mechanism already used for any other stated slot correction —
  no separate "calendar vs. user" precedence rule.
- **FR-011**: None of the above MUST alter an already-in-progress conversation's accumulated
  state — the fresh-thread gate in FR-005/FR-009 applies per-thread, not retroactively.
- **FR-012**: `design-system.md` § "Connected, has events" row-dimming behavior (all rows
  disabled once any event is picked) MUST remain unchanged.

### Key Entities

- **Picked event** (existing, `picked_events` table / `PickedEventSnapshot`): one per user,
  holds `google_event_id`, `title`, `start_time`, `location`. Unchanged by this feature —
  only which callers *read* it changes (the styling route now reads it; the frontend gains a
  write-through cache of it instead of a mount-scoped fetch).
- **Conversation slot state** (existing, the LangGraph checkpoint keyed by `thread_id`):
  gains exactly one new writer — `POST /recommend/turns` seeding `location` once, on a
  thread's first turn, from the caller's picked event when one exists. No new fields, no
  schema change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who picks an event reaches the Recommend screen with no manual
  navigation step, 100% of the time the save succeeds.
- **SC-002**: The picked-event label shown on Recommend matches the server's actual current
  picked event on every arrival at the screen, including via in-app navigation — never stale
  by more than one request's round-trip.
- **SC-003**: In a fresh conversation with a picked event that has a location, the first
  conversational reply does not re-ask for that location.
- **SC-004**: A styling request on a fresh thread with a picked event uses that event's
  location for weather-aware context, verifiable by comparing the assembled `Context`'s
  weather fields against a direct `assemble_context(location=...)` call for the same
  location.
- **SC-005**: A failed pick save never leaves the Calendar screen in a state indistinguishable
  from a successful one (verified by an explicit test asserting rows re-enable and an error
  surfaces).

## Assumptions

- **No real Google Calendar OAuth credentials were available to exercise end-to-end against a
  live Google account in this unattended run beyond what was already configured in this
  environment's `backend/.env`.** Verification instead uses the existing mocked
  integration/unit test doubles this codebase already has for the calendar routes/repository,
  plus a manual browser pass against the local dev stack seeding a picked event directly via
  the already-existing `PUT /api/v1/calendar/picked-event` endpoint (which requires only a
  signed-in test user, not a completed Google OAuth round-trip). This is recorded explicitly
  in the final report rather than silently asserted as full coverage.
- Design decision for defect 3 (which slots the event fills, and how) is settled in
  `docs/design-decisions.md` §61 and treated as binding for this spec, not re-litigated here.
- The "way to change/clear" a picked event, named in the GitHub issue's acceptance criteria,
  is read as "preserve the existing Change link," not as a request for new unpick UI — see
  §61's explicit scope boundary and this spec's Edge Cases.
- `EventRow`'s existing time/date formatting (`formatEventTime`) is reused verbatim for the
  Composer pre-fill text, rather than introducing a second time-formatting convention.
- This feature does not touch `pipeline/`, `scoring/`, or `retrieval/` (Constitution I) — the
  backend change is additive wiring in `recommend.py` (one more repository read, one more
  `graph.update_state` call) with no change to `context_assembler.assemble_context`'s
  existing signature or behavior.
