# Feature Specification: Styling chat

**Feature Branch**: `008-styling-chat`

**Created**: 2026-08-01

**Status**: Draft

**Input**: User description: "Feature 008: Styling chat. Per docs/handoffs/008-styling-chat.md: a user
types a plain-English styling request (\"business casual for a rainy commute\") on the /recommend
screen and gets back a single outfit built from their own closet, with reasoning that cites real
styling rules from the knowledge base. This wires the already-complete, evaluated LangGraph
pipeline (pipeline/graph.py, zero callers today) to one new backend route and the Recommend
screen's chat surface (hero state, chat state, calendar context line, \"Start styling\" button,
pinned input bar) per design/design-system.md's Screen anatomy → Recommend section. Renders the
single top-ranked outfit from ScoredOutfit list (the multi-outfit pager is feature 009, explicitly
out of scope). Includes the insufficient-closet gate (enforced server-side), thread persistence
via the existing checkpointer, and citations rendered inline in the assistant bubble (never on an
outfit card, per design-system § Badge). Full scope, out-of-scope list, constraints and traps are
in the handoff — treat it as authoritative and do not re-derive scope."

## Clarifications

### Session 2026-08-01

- Q: What's the maximum time a user should wait for a styling reply before the request is
  treated as timed out and shown an error (with retry)? → A: No fixed, user-facing artificial
  cap on wait time.
- Q: Given the handoff's explicit warning against repeating the calendar slice's
  uncapped-latency gap, does "no cap" mean truly unbounded, or no UX-driven cap while still
  keeping a generous backstop so a stuck request can't hang forever? → A: Generous backstop
  only — no tight UX timeout, but a backstop timeout (recommended ~120s) at the request layer
  so a genuinely stuck request eventually surfaces as a retryable error rather than hanging
  indefinitely.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ask for an outfit and get a grounded, cited suggestion (Priority: P1)

A signed-in user with enough clothes in their closet opens Styling, types a plain-English request
("business casual for a rainy commute"), and gets back one outfit assembled entirely from items
they actually own, with a written explanation that cites real styling principles and a row of
tappable thumbnails for the items used.

**Why this priority**: This is the app's entire value proposition — the pipeline exists and is
evaluated, but nothing has ever called it from a real user action. Without this story nothing else
in the feature matters.

**Independent Test**: With a closet that clears the readiness gate (see User Story 3) and the
knowledge base populated, send one styling request and confirm the reply contains only owned
items, cites at least one real rule, and every citation traces to something actually retrieved.

**Acceptance Scenarios**:

1. **Given** a first-time visit to Styling with no prior conversation, **When** the screen loads,
   **Then** the user sees a welcome bubble, three example prompts, and a greeting that matches the
   current time of day.
2. **Given** the hero state, **When** the user types "business casual for a rainy commute" and
   sends it, **Then** a transient acknowledgement appears, followed by a single assistant reply
   containing outfit reasoning, inline numbered citations, a thumbnail row of the items used, and
   (when the reply cites rules) a list explaining each cited rule.
3. **Given** a returned outfit, **When** the user taps one of the item thumbnails, **Then** they
   land on that item's own detail view.
4. **Given** a styling request that cannot produce a viable outfit, **When** the pipeline returns
   no result, **Then** the user sees an honest message rather than a fabricated outfit or a raw
   error.
5. **Given** a styling request that fails outright (the request never reaches a result), **When**
   the failure occurs, **Then** the user sees an error message with a way to retry the same
   request.

---

### User Story 2 - Refine the outfit through the same conversation (Priority: P2)

Having received a first suggestion, the user sends a follow-up ("something warmer") in the same
conversation and gets back a revised suggestion that accounts for what was already discussed,
rather than starting over from a blank slate.

**Why this priority**: A styling conversation that forgets itself after one exchange is a materially
worse product than the one the pipeline was actually built and evaluated to support (thread-aware
refinement).

**Independent Test**: Send a first message, wait for the reply, send a second, and confirm the
second reply is a refinement of the first rather than an unrelated fresh suggestion.

**Acceptance Scenarios**:

1. **Given** an assistant reply already on screen, **When** the user sends a second message in the
   same conversation, **Then** the reply reflects the earlier context rather than treating the
   message as a brand-new, unrelated request.
2. **Given** an ongoing conversation, **When** the user reloads or returns to Styling later in the
   same session, **Then** the prior exchange is still visible and refinement still works against
   it (subject to the persistence guarantee described in the plan).

---

### User Story 3 - Blocked when the closet isn't ready yet (Priority: P2)

A user whose closet does not yet have enough of the right kinds of items to assemble an outfit
sees a clear explanation of what is missing and a way to fix it, instead of being allowed to send
a request that can only fail.

**Why this priority**: Letting an under-stocked closet through to the pipeline produces a
confusing, unexplained failure — this gate protects the P1 experience from looking broken.

**Independent Test**: With a closet that does not clear the readiness bar, open Styling and
confirm the composer is replaced by the insufficient-closet message before any request is sent,
and confirm the same block holds even if the client-side check is bypassed.

**Acceptance Scenarios**:

1. **Given** a closet that does not clear the readiness bar, **When** the user opens Styling,
   **Then** they see an explanation of what is missing and a way to add items, and the composer
   does not accept a styling request.
2. **Given** a closet that clears the bar but is still small, **When** the user opens Styling,
   **Then** the composer works normally, optionally alongside a dismissible note that suggestions
   may repeat until the closet grows.
3. **Given** a request sent while the closet does not clear the bar (bypassing the client-side
   gate entirely), **When** the request reaches the server, **Then** it is rejected the same way
   the UI gate would have prevented it, and the pipeline is never invoked.

---

### User Story 4 - Start a fresh conversation (Priority: P3)

The user wants to abandon the current thread and start over, distinct from continuing to refine
it.

**Why this priority**: Necessary for the chat to feel usable across multiple, unrelated styling
needs in one sitting, but the app is still useful without it on day one.

**Independent Test**: Send at least one message, trigger "New chat," and confirm the screen resets
to the hero state while the prior conversation remains reachable later (per whatever history
mechanism is in place).

**Acceptance Scenarios**:

1. **Given** a conversation with no user messages yet (fresh hero state, or right after a reset),
   **When** the user looks at "New chat," **Then** it is visibly present but disabled/inert.
2. **Given** a conversation with at least one user message, **When** the user selects "New chat,"
   **Then** the current thread is preserved for later and the screen returns to the hero state
   with a fresh, empty thread.

---

### User Story 5 - Style for a calendar event (Priority: P3)

A user with a connected calendar and a picked upcoming event sees that context surfaced on
Styling, so a request can take the event into account without retyping its details.

**Why this priority**: A nice accelerator on top of the core chat, not required for the core value
to work — calendar connection and event-picking themselves are already built by a prior feature.

**Independent Test**: With a picked calendar event present, open Styling and confirm the
event context line appears and reflects that event; with none picked, confirm the line invites
picking one instead.

**Acceptance Scenarios**:

1. **Given** no calendar event has been picked, **When** the user views Styling, **Then** they see
   an invitation to style for an event from their calendar.
2. **Given** an event has been picked elsewhere in the app, **When** the user views Styling,
   **Then** they see that event named on the context line with a way to change it.

---

### Edge Cases

- What happens when the user sends a message while offline? The composer must not accept the
  send; no message is queued and no copy promises a later retry.
- What happens when the user sends a second message before the first reply has finished? The
  composer must not allow a second concurrent send while one is in flight.
- What happens when the knowledge base has nothing relevant to retrieve for a request? The reply
  must not fabricate a citation — an outfit with nothing honest to cite is returned with no
  citations rather than an invented one.
- What happens when a styling request takes several seconds (the expected case, not a fault)? The
  user must see an in-progress indication the whole time, not a silently hanging composer. There
  is no user-facing artificial wait cap — the request is allowed to take as long as the pipeline
  genuinely needs — but a generous backstop timeout still exists so a request that is truly stuck
  (not just slow) eventually surfaces as a retryable error instead of hanging forever.
- What happens if the conversation is reloaded after the assistant's thread state cannot be found
  (e.g. it was never durably persisted)? The user sees a fresh hero state rather than a broken
  or partially-rendered thread.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST let a signed-in user submit a free-text styling request from the
  Styling screen's composer.
- **FR-002**: The system MUST build every suggested outfit exclusively from items the requesting
  user owns (or the shared catalog, per existing grounding rules) — never an invented item.
- **FR-003**: The system MUST attach the assistant's reasoning to real, retrieved styling
  citations, and MUST return an honest empty citation list rather than a fabricated one when
  nothing grounds the reasoning.
- **FR-004**: The system MUST render exactly one outfit suggestion per assistant reply in this
  feature (the multi-outfit pager is out of scope).
- **FR-005**: The system MUST show, for a rendered outfit, a thumbnail per item that links to that
  item's own detail view.
- **FR-006**: The system MUST render inline numbered citation markers and a supporting rule list
  in the assistant's chat bubble, and MUST NOT render citation markers on an outfit-suggestion
  card.
- **FR-007**: The system MUST block a styling request server-side whenever the requesting user's
  closet does not satisfy the readiness bar, independent of whatever client-side gate also exists,
  and MUST NOT invoke the styling pipeline for a blocked request.
- **FR-008**: The system MUST explain, in the blocked state, what kind of item is missing rather
  than only a bare item count.
- **FR-009**: The system MUST let a second message in the same conversation refine the prior
  suggestion rather than always starting a fresh, context-free request.
- **FR-010**: The system MUST let the user explicitly start a new conversation, distinct from
  refining the current one.
- **FR-011**: The system MUST keep "New chat" visible but disabled whenever the current thread has
  no user messages yet, rather than hiding the control.
- **FR-012**: The system MUST show a transient in-progress indication for the length of a styling
  request, and MUST NOT allow a second concurrent send while one is already in flight.
- **FR-013**: The system MUST disable sending while the client is offline, and MUST NOT queue a
  message or promise a later automatic retry.
- **FR-014**: The system MUST show the assistant's welcome state (brand mark, wordmark, greeting,
  welcome bubble, example prompts) before the user's first message, with the greeting matching the
  current time of day.
- **FR-015**: The system MUST surface the user's picked calendar event (when one exists) as
  context on the Styling screen, and MUST offer to pick one when none exists.
- **FR-016**: The system MUST NOT display a numeric score, percentage, or raw model output
  anywhere on the Styling screen.
- **FR-017**: The system MUST show a distinct, actionable message when a styling request produces
  no viable outfit, and a distinct, actionable message (with retry) when the request fails
  outright — the two must not be presented identically.
- **FR-018**: The system MUST NOT claim or imply personalization based on past feedback anywhere
  in this feature's UI, since preference memory is not wired into the pipeline in this slice.
- **FR-019**: The system MUST NOT impose a tight, user-experience-driven wait cap on a styling
  request — the user waits as long as the pipeline genuinely takes — but MUST enforce a generous
  backstop timeout so a genuinely stuck request eventually fails with a retryable error instead of
  hanging indefinitely.

### Key Entities

- **Styling request**: a user's free-text ask, plus whatever conversation/thread context it is
  interpreted within.
- **Styling reply**: the assistant's response — reasoning text, zero or more citations to styling
  rules, and (when successful) exactly one suggested outfit.
- **Suggested outfit**: a set of the user's own closet items assembled to answer a styling
  request, together with a match quality expressed only as a label, never a number.
- **Conversation / thread**: the ongoing exchange a styling request and its refinements belong to;
  has a lifecycle (starts at the hero state, can be explicitly reset by "New chat").
- **Closet readiness**: a derived state of the user's closet (whether it has enough of the right
  kinds of items) that gates whether a styling request may be sent at all.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with a ready closet can go from typing a styling request to seeing a
  complete, cited outfit suggestion without any error, in a single conversation turn.
- **SC-002**: 100% of items shown in any styling reply belong to the requesting user's own closet
  or the shared catalog — never an invented item.
- **SC-003**: 100% of citations shown in a styling reply trace back to something the system
  actually retrieved for that request — never a fabricated citation.
- **SC-004**: A user whose closet is not ready is blocked from sending a styling request in 100%
  of cases, including when the normal UI gate is bypassed.
- **SC-005**: A user can carry out at least one follow-up refinement in the same conversation and
  perceive the assistant as responding to what was already said, not starting over.
- **SC-006**: No screen in this feature ever displays a raw number or percentage representing
  outfit quality.
- **SC-007**: A user attempting to send while offline is prevented from doing so, with no silent
  failure and no false promise of a later retry.

## Assumptions

- The styling pipeline (retrieval, scoring, generation, grounding, citation enforcement) already
  exists, is already evaluated, and is treated as a correct, unmodified dependency of this
  feature — this feature is responsible for calling it, not for changing its behavior.
- "Closet readiness" is a derived condition (adequate coverage of outfit-forming item types, not a
  bare item count) per the project's own prior resolution of this exact gate; this spec assumes
  that resolution rather than re-deriving it.
- Calendar connection and event-picking already exist as a prior feature; this feature only
  consumes the picked event, it does not build calendar connection itself.
- Item detail, closet browsing, and authentication already exist as prior features this one links
  to and depends on.
- Exactly one outfit is rendered per reply in this feature; multiple simultaneous suggestions
  (the pager) are a separate, later feature and explicitly out of scope here.
- Chat history as its own browsable screen is a separate, later feature; this feature only needs
  "New chat" to behave sensibly, not to build a history screen.
- A styling request is expected to take multiple seconds end to end; this is treated as normal
  latency to be communicated clearly, not as a defect to eliminate.
