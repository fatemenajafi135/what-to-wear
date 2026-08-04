# Feature Specification: Conversational styling turns

**Feature Branch**: `feat/016-conversational-turns`

**Created**: 2026-08-04

**Status**: Draft

**Input**: User description: "Feature 016 — Conversational styling turns. The Recommend chat should be
an actual back-and-forth conversation before the user taps 'Start styling' — every composer send gets
a real, in-voice assistant reply that acknowledges what it heard and asks for what's still missing,
while accumulating what the user has told it. 'Start styling' remains the one trigger that produces
outfits, now preceded by a visible wrap-up of what was understood. See docs/handoffs/016-
conversational-turns.md and docs/design-decisions.md §37 (amending §28) for full context."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The stylist actually replies (Priority: P1)

A user opens Recommend and types a message describing what they need help with. Instead of the
message just sitting in the transcript until they tap "Start styling," the stylist replies —
acknowledging what it understood and, if something useful is still missing, asking one focused
follow-up question.

**Why this priority**: This is the entire feature. Without a reply, nothing else in this slice has
any user-visible effect.

**Independent Test**: Send one message in Recommend and confirm an assistant bubble appears with a
reply before "Start styling" is ever tapped.

**Acceptance Scenarios**:

1. **Given** an empty conversation, **When** the user sends a message describing an occasion, **Then**
   an assistant reply appears acknowledging it and, if formality/weather/mood is still unknown, asking
   about one of them.
2. **Given** the user has already stated the occasion, **When** they send a second message answering
   the assistant's follow-up, **Then** the next reply does not ask about something already answered.
3. **Given** the assistant has gathered enough to proceed, **When** the user sends another message,
   **Then** the reply tells them they can tap "Start styling" whenever ready, rather than continuing
   to ask questions.

---

### User Story 2 - What I said earlier is what gets used (Priority: P1)

A user has a multi-turn conversation — mentioning the occasion in one message and the formality or
weather in a later one — then taps "Start styling." The outfits reflect everything discussed, not
just the most recent message.

**Why this priority**: A conversation that doesn't change the outcome is theater. This is the
functional payoff of User Story 1, and the handoff calls out that verifying it end-to-end (not just
eyeballing the outfits) is a hard requirement.

**Independent Test**: Have a conversation stating the occasion in turn 1 and the formality in turn 2,
tap "Start styling," and confirm (by inspecting what was actually sent to generate outfits, not just
by looking at the results) that both values were used.

**Acceptance Scenarios**:

1. **Given** a conversation where the occasion was stated in an early turn and formality in a later
   turn, **When** the user taps "Start styling," **Then** both values are present in what the system
   uses to generate outfits.
2. **Given** a later message repeats or changes an earlier answer (e.g. "actually, make it more
   casual"), **When** the next reply or "Start styling" happens, **Then** the most recently stated
   value wins.
3. **Given** the user never mentions a particular detail (e.g. never states a location), **When**
   "Start styling" is tapped, **Then** the system proceeds without inventing one.

---

### User Story 3 - Start styling shows its work (Priority: P2)

Before the outfits appear, the user sees a short assistant message summarizing what the system
understood — so a wrong or incomplete read is visible and correctable rather than only inferable from
bad results.

**Why this priority**: Trust and debuggability for the user; secondary to the conversation itself and
to outfits reflecting the conversation, but part of what makes this feature more than an invisible
plumbing change.

**Independent Test**: Have a short conversation, tap "Start styling," and confirm a wrap-up message
renders as its own assistant bubble immediately before the outfit results, and still renders
sensibly when some detail was never mentioned.

**Acceptance Scenarios**:

1. **Given** a conversation with at least an occasion stated, **When** the user taps "Start styling,"
   **Then** a wrap-up message appears as an assistant bubble before the outfits load.
2. **Given** some detail (e.g. formality) was never mentioned, **When** the wrap-up renders, **Then**
   it reads sensibly without that detail rather than showing a placeholder or blank.

---

### User Story 4 - The conversation doesn't stall or run away (Priority: P2)

The composer clearly shows when a reply is in flight (so the user doesn't double-send or think the
app is broken), and the back-and-forth doesn't continue indefinitely — after enough turns, the
assistant steers the user toward "Start styling" instead of continuing to converse. If a reply fails,
the user isn't stuck — "Start styling" still works with whatever was already understood.

**Why this priority**: Guards the cost and reliability of the new conversational calls; needed for
the feature to be safe to ship, but not the primary value proposition.

**Independent Test**: Send a message and confirm the composer disables and shows an in-progress state
until the reply lands; have a long conversation and confirm it is steered toward "Start styling"
after a bounded number of turns; simulate a failed reply and confirm "Start styling" still produces
outfits from what was gathered so far.

**Acceptance Scenarios**:

1. **Given** a message has just been sent, **When** the reply is in flight, **Then** the input and
   send control are both disabled and show a visible in-progress state, and both re-enable the instant
   the reply lands.
2. **Given** the user keeps chatting past a bounded number of turns, **When** the cap is reached,
   **Then** the assistant's reply steers them to tap "Start styling" rather than asking another
   question.
3. **Given** a conversational reply fails to arrive, **When** the user looks at the chat, **Then** it
   is left in a usable state and "Start styling" still works with whatever was gathered before the
   failure.
4. **Given** the device is offline, **When** the user looks at the composer, **Then** it is disabled
   and no message is queued or promised to send later.

### Edge Cases

- The very first message in a conversation is itself the answer to a question that hasn't been asked
  yet (e.g. "something casual for brunch, 60 degrees out") — the reply must not re-ask for what was
  already given.
- A user's message doesn't map cleanly to any tracked detail (small talk, an unrelated question) —
  the reply must still be a plausible in-voice response, must not fabricate a slot value, and must not
  block "Start styling."
- The user taps "Start styling" after only one message with no assistant reply yet exchanged — this
  must still work exactly as it does today, using whatever was said.
- The user has a long conversation, taps "Start styling," and then keeps chatting on the same
  thread — the next reply and the next "Start styling" tap must behave predictably with respect to
  what was gathered before the first tap (defined precisely in the implementation plan, not left
  ambiguous here).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST generate a reply to every message the user sends in the composer, before
  "Start styling" is tapped, without requiring a wardrobe lookup or producing outfits.
- **FR-002**: Every reply MUST be written in the app's established first-person stylist voice, MUST
  ask at most one clarifying question, and MUST NOT promise anything the system cannot ultimately
  deliver.
- **FR-003**: The system MUST track, across the whole conversation, what it has already learned about
  the request (at minimum: occasion, formality, mood, weather/temperature, location) and MUST NOT
  re-ask for something already known.
- **FR-004**: When a later message provides a new value for something already known, the newer value
  MUST take precedence over the earlier one.
- **FR-005**: "Start styling" MUST remain the only user action that produces outfits, and the outfits
  it produces MUST be generated from everything learned across the conversation, not only the most
  recent message.
- **FR-006**: If nothing usable was ever learned from the conversation, "Start styling" MUST still
  produce a result using the same fallback behavior the system has today (treating the raw message
  text as the request).
- **FR-007**: Immediately before outfits are generated, the system MUST show the user a summary
  message of what it understood, and that summary MUST degrade gracefully (read sensibly, not show a
  placeholder) when some detail was never mentioned.
- **FR-008**: While a reply is being generated, the system MUST prevent the user from sending another
  message or tapping "Start styling" concurrently, MUST show a visible in-progress indication distinct
  from the indication shown while outfits are being generated, and MUST re-enable input the instant
  the reply arrives.
- **FR-009**: The system MUST cap the number of conversational back-and-forth turns allowed per
  conversation; upon reaching the cap, the reply MUST steer the user toward "Start styling" instead of
  asking another question. This cap MUST be a configurable value, not a hardcoded constant.
- **FR-010**: If generating a conversational reply fails, the system MUST leave the conversation in a
  usable state and MUST NOT prevent "Start styling" from working with whatever was already learned.
- **FR-011**: While offline, the composer MUST be disabled and MUST NOT imply a message will be sent
  or queued for later.
- **FR-012**: The system MUST NOT invent or ship final user-facing wording for the assistant's
  ordinary conversational replies on its own — that copy is supplied by the design owner. Until it is
  supplied, any placeholder text used for development MUST be clearly identifiable as non-final in the
  codebase and MUST NOT be presented as though it were finished, reviewed copy.
- **FR-013**: The conversational reply-generation step MUST NOT alter the existing outfit-generation
  behavior, ranking, or wording produced once "Start styling" is tapped — it only supplies additional
  input to that unchanged process.

### Key Entities

- **Conversational turn**: One user message and its assistant reply, prior to "Start styling." Carries
  the reply's visible text plus whatever it added or changed in the accumulated understanding of the
  request.
- **Accumulated request understanding ("slots")**: The evolving, per-conversation record of what has
  been learned so far (occasion, formality, mood, weather/temperature, location) — the input "Start
  styling" composes its request from.
- **Wrap-up**: The one-time summary message shown at the moment "Start styling" is tapped, describing
  the accumulated understanding at that point.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of composer sends receive a visible assistant reply before "Start styling" is
  tapped (excluding a genuine send failure, which still leaves the app usable).
- **SC-002**: In a conversation where a request detail is stated in an earlier turn and a different
  detail in a later turn, both are reflected in the outfits "Start styling" produces — verified
  directly against what the outfit-generation step receives, not inferred from the results shown to
  the user.
- **SC-003**: No assistant reply ever asks about a detail the user has already provided earlier in the
  same conversation.
- **SC-004**: A conversation cannot exceed its configured turn cap without being steered toward "Start
  styling" instead of continuing indefinitely.
- **SC-005**: A failed conversational reply never blocks "Start styling" from producing outfits.

## Assumptions

- This feature extends the existing Recommend chat (feature 008) and its persisted chat history
  (feature 011); it does not introduce a new screen or entry point.
- "Start styling" continues to be the sole trigger for real outfit generation — this feature adds a
  cheaper, separate reply step before it, not a second way to produce outfits.
- The set of details the system tracks across a conversation (occasion, formality, mood, weather/
  temperature, location) matches what the existing outfit-generation step already accepts today; this
  feature does not introduce new kinds of request detail.
- Feeding the conversation into longer-term personalization/preference learning is out of scope for
  this slice.
- Voice input and token-by-token streaming of the reply are out of scope for this slice.
- Final, reviewed wording for the assistant's ordinary conversational replies may not be available
  before this feature is otherwise ready to ship; the feature must be buildable and demonstrable with
  clearly-marked placeholder wording in that case.
