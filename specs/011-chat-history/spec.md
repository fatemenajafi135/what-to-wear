# Feature Specification: Chat history

**Feature Branch**: `011-chat-history`

**Created**: 2026-08-03

**Status**: Draft

**Input**: User description: "Chat history (feature 011): persist styling conversations so a user can reload the page, find a past conversation in a new Chat history screen, reopen it read-only with citation badges, and continue it into a live thread. See docs/handoffs/011-chat-history.md."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A conversation survives a reload (Priority: P1)

A user chats with the styling assistant, gets a reply, then reloads the page (or returns later).
Today the whole conversation — and the `thread_id` the pipeline was tracking it under — is gone.
They can now open Chat history and find that exact conversation.

**Why this priority**: This is the mission (handoff §1) and the gap named in
design-decisions.md §25. Nothing else in this feature matters if a conversation still
disappears on reload.

**Independent Test**: Send at least one message in Recommend, reload the page, open Chat
history from the Recommend header, and confirm the conversation is listed.

**Acceptance Scenarios**:

1. **Given** a user has sent at least one message in a styling conversation, **When** they
   reload the page and open Chat history, **Then** that conversation appears in the list,
   without requiring any explicit "save" or "archive" action first.
2. **Given** a fresh Recommend screen with only the greeting shown (no user message sent yet),
   **When** the user reloads or navigates away without sending anything, **Then** nothing new
   appears in Chat history.

---

### User Story 2 - Browse and reopen a past conversation (Priority: P1)

A user opens Chat history, sees a list of past conversations (most recent first), and taps one
to read it back in full.

**Why this priority**: Without this, persistence (Story 1) has no user-facing surface — the
data exists but nobody can see it.

**Independent Test**: With two or more past conversations, open Chat history and verify each
row shows a preview, date, and message count; tap one and verify the full thread renders
read-only.

**Acceptance Scenarios**:

1. **Given** at least one past conversation exists, **When** the user opens Chat history,
   **Then** they see a row per conversation with a preview line, a date, and a message-count
   line, most recently active conversation first.
2. **Given** a conversation that produced at least one outfit, **When** its row renders,
   **Then** a third line shows the outfit count in the primary accent color.
3. **Given** a conversation that produced no outfits, **When** its row renders, **Then** no
   third line appears.
4. **Given** the user taps a session row, **When** Session detail opens, **Then** the full
   thread renders read-only, in arrival order, with the same bubble treatment Recommend uses,
   including citation badges where the original reply had citations — but with no
   item-thumbnail rows and no rule list, even where the live Recommend screen would have shown
   them.
5. **Given** the Chat history list has no conversations yet, **When** the user opens it,
   **Then** it shows the specified empty-state copy, no error.
6. **Given** the Chat history request fails, **When** the user opens Chat history, **Then** it
   shows the specified error copy with a retry action.

---

### User Story 3 - Continue a past conversation (Priority: P1)

From Session detail, the user taps "Continue conversation" and lands back in Recommend, able to
send a new message that refines the *same* conversation rather than starting a new one.

**Why this priority**: Read-only history alone doesn't close the actual gap named in the
handoff mission ("I reopen a past conversation, read it back, **and continue it**"). Without
this, Chat history is a dead-end log, not a resumable conversation.

**Independent Test**: Open a past session, tap "Continue conversation," send a follow-up
message, and inspect the outgoing request to confirm it carries the same `thread_id` the
session was archived under (not a freshly minted one).

**Acceptance Scenarios**:

1. **Given** a past session, **When** the user taps "Continue conversation," **Then** Recommend
   opens with that session's thread active, ready to accept a new message.
2. **Given** the user sends a follow-up after continuing, **When** that request reaches the
   backend, **Then** it carries the original session's `thread_id`, not a new one — verified by
   inspecting the request, not just by reading a plausible-looking reply.

---

### User Story 4 - Start a new conversation without losing the old one (Priority: P2)

From Recommend, the user taps "New chat." The current conversation (if it has any user turns)
is already durably saved, and the visible thread resets to the greeting so the user can start
fresh.

**Why this priority**: This is existing UI (008/009 already built the reset and the disabled
guard); 011 only needs to confirm the guard's premise ("nothing to archive") is now backed by
real, already-durable data rather than changing the button's behavior.

**Independent Test**: Send a message, tap "New chat," reload, and confirm the prior
conversation is in Chat history while Recommend shows a fresh greeting with no `thread_id` held.

**Acceptance Scenarios**:

1. **Given** a thread with at least one user message, **When** the user taps "New chat,"
   **Then** Recommend resets to the greeting state and the prior conversation remains found in
   Chat history exactly as it was.
2. **Given** a fresh greeting with no user turns yet, **When** the user looks at "New chat,"
   **Then** it is visibly present but disabled, and activating it has no effect.

---

### User Story 5 - Jump from a session to the outfits it produced (Priority: P3)

From Session detail, when the conversation produced at least one outfit, the user taps a
"View in Outfits" button and lands on the Outfits gallery.

**Why this priority**: Useful, but Stories 1-3 deliver the core mission without it; this is a
convenience link on top of already-persisted data.

**Independent Test**: Open a session that produced an outfit, confirm the button's count
matches the number of outfits that session produced, and confirm tapping it navigates to
Outfits.

**Acceptance Scenarios**:

1. **Given** a session that produced outfits, **When** Session detail renders, **Then** a
   full-width secondary button reads "{count} → View in Outfits" below the thread.
2. **Given** a session that produced no outfits, **When** Session detail renders, **Then** no
   such button appears.

---

### Edge Cases

- A session that predates this feature has no recoverable link to any outfit it may have
  produced (the link did not exist yet) — it must never appear to have produced outfits it
  cannot actually be tied back to, and must never claim a false or guessed count.
- A conversation where the assistant's reply had nothing groundable to cite: the archived
  bubble shows no citation badges for that reply, matching the honest-empty-citation behavior
  the rest of the product already uses — never a fabricated citation.
- The device is offline when Chat history or Session detail is opened: the global offline
  banner applies and the screen must not also show its own error copy for the same root cause.
- A session with zero outfits: no third preview line, no "View in Outfits" button — never a
  "0" shown as if it were a real count.
- Continuing a conversation, then sending a message that itself produces new outfits: those
  outfits must link back to the same session as the ones already shown for it, so the count
  grows rather than the session appearing to fork into two.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST persist a conversation durably from the moment a user sends their
  first message in it — not only when the user takes an explicit "archive" or "new chat"
  action.
- **FR-002**: The system MUST NOT create a persisted conversation record for a thread that has
  received no user message (a fresh greeting alone is never archived).
- **FR-003**: Users MUST be able to list their own past conversations, most recently active
  first, each showing a preview of the conversation, its date, and how many messages it
  contains.
- **FR-004**: Users MUST be able to open a single past conversation and read its full
  transcript, in the order the messages occurred, without being able to edit or delete any of
  it from this feature.
- **FR-005**: The archived transcript view MUST render citation badges on an assistant turn
  that had citations at the time it was produced, sourced from that turn's own persisted
  citation data — but MUST NOT render item-thumbnail rows or a numbered rule list for that
  turn, even though live Recommend / Outfit detail would show related information alongside
  citations.
- **FR-006**: Users MUST be able to resume a past conversation such that their next message is
  attributed to the same underlying conversation thread as the one they resumed, not a new one.
- **FR-007**: When a past conversation produced one or more outfits, the system MUST show how
  many, both in the conversation's list row and in its detail view, and MUST let the user
  navigate from the detail view to the Outfits gallery.
- **FR-008**: When a past conversation produced no outfits, the system MUST NOT show an outfit
  count or a link to Outfits for it.
- **FR-009**: A conversation that predates this feature's outfit-linking mechanism MUST show as
  having produced no outfits (never a guessed or backfilled count), even if outfits were in
  fact generated from it before this feature existed.
- **FR-010**: "New chat" MUST remain disabled whenever the active thread has no user turns, and
  MUST continue to reset the visible conversation to the greeting state when activated,
  exactly as it does today.
- **FR-011**: A user MUST only ever be able to list or read their own conversations, never
  another user's — enforced independently of any single backend connection's own privileges.
- **FR-012**: Chat history and Session detail MUST each support loading, empty (list only),
  error, and offline states, with the empty and error copy matching the product's specified
  text exactly.
- **FR-013**: Persisting a conversation or linking an outfit to it MUST NOT alter the behavior,
  inputs, or outputs of outfit generation itself (retrieval, scoring, or the pipeline).

### Key Entities

- **Session**: One durable record per styling conversation thread. Identified by the same
  `thread_id` the pipeline already mints (never a second, independently generated id). Owned by
  exactly one user. Exists from the first user message in that thread onward.
- **Message**: One durable record per turn in a session — a user's own message, or an
  assistant's reply. Ordered by when it occurred. Carries a discriminator for what kind of
  turn produced it, so that future turn kinds (not part of this feature) can be added without
  reshaping this record.
- **Outfit** *(existing entity, extended)*: Gains an optional link back to the session that
  produced it. A pre-existing outfit has no such link and is never treated as belonging to any
  session.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who has one styling exchange and reloads the page can find that exact
  conversation in Chat history 100% of the time, with no manual save step.
- **SC-002**: Reopening any past conversation reproduces its full transcript, in order, with no
  missing turns, on every attempt.
- **SC-003**: Continuing a past conversation and sending a follow-up results in that follow-up
  being attributed to the original conversation's thread, verified at the request level, 100%
  of the time.
- **SC-004**: A conversation's displayed outfit count always matches the number of outfits
  that can be verified (by a durable link, not a guess) to have come from it — never an
  overcount, never a fabricated count for a conversation that predates the link.
- **SC-005**: No user can read another user's conversation or its messages under any tested
  access path, including one that bypasses the application's own database connection
  privileges.

## Assumptions

- One session maps one-to-one with one pipeline `thread_id`; there is no concept of merging or
  splitting sessions in this feature.
- A session's "most recently active" ordering is based on when its last message was written,
  not only when it was first created — a continued, older conversation moves back to the top.
- Editing a session's content, deleting a session, and searching across sessions are explicitly
  out of scope (per the handoff); nothing in this spec requires them.
- Feature 016 (conversational turns, already scoped separately) will later add new message
  kinds and a new endpoint; this feature only reserves room for that in the data shape and
  builds none of 016's own behavior.
- The two decisions the handoff names as this feature's own to make — what a session is/what
  writes it, and how outfits link back to their conversation, including what a pre-existing
  outfit shows — are resolved during planning and recorded in `docs/design-decisions.md`
  starting at §44, not guessed silently in code.
- "Message count" on a session row counts every turn in the conversation (both the user's own
  messages and the assistant's replies), not user turns alone — the most literal reading of
  the design system's "message-count text" and consistent with a session's Message entity
  covering both roles.
