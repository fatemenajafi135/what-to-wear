# Feature Specification: Recommend Chat Persists Across In-App Navigation

**Feature Branch**: `feat/019-recommend-chat-persistence`

**Created**: 2026-08-11

**Status**: Draft

**Input**: User description: "The Recommend screen's styling chat resets when the user navigates away and back. The conversation itself is NOT lost — it's durable via the LangGraph checkpointer and chat_history (backend). The screen just re-fetches and re-renders from scratch on remount, so it FEELS lost. Fix: the conversation stays alive across in-app navigation. It resets only on app close + reopen (a real reload) or an explicit 'New chat' tap." (GitHub issue #47)

## Clarifications

### Session 2026-08-11

- Q: Should the Closet-readiness check (the gate deciding hero/chat vs. "add more items," and the sparse-closet banner) re-run every time the user returns to Recommend, or be held in persisted state and skipped on return? → A: Refetch every return — only the conversation itself is preserved; readiness always reflects the closet's current state.
- Q: Should the "Start styling" error card ("Something went wrong pulling that together" + Try again) still be showing if the user navigates away right after it appears, then comes back? → A: Yes, preserve it — it's part of the conversation's current state, same as any pending/sent message.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conversation survives a trip to another tab (Priority: P1)

A user is mid-conversation on Recommend — they've sent a couple of messages, maybe tapped
"Start styling" and seen outfits — then taps over to Closet (or any other tab) to check
something, and taps back to Recommend.

**Why this priority**: This is the entire bug report. Without this, the feature does nothing.

**Independent Test**: Send at least one composer message on Recommend, navigate to any other
primary destination (Closet, Outfits, Profile), navigate back to Recommend. The conversation —
every message bubble, the thread identity, and any outfits already produced — is exactly as it
was left, with no loading flash and no re-fetch.

**Acceptance Scenarios**:

1. **Given** a Recommend conversation with at least one sent message and one assistant reply,
   **When** the user navigates to Closet and back to Recommend, **Then** the same messages are
   still rendered in the same order, with no hero (empty) state shown in between.
2. **Given** a Recommend conversation where "Start styling" has already produced outfits,
   **When** the user navigates away and back, **Then** the outfit results and the wrap-up
   message are still present exactly as before.
3. **Given** a composer send or a "Start styling" call is still in flight (its response has not
   yet arrived), **When** the user navigates away and back before it resolves, **Then** the
   response is applied to the persisted conversation when it arrives, whether or not Recommend
   is the visible screen at that moment, and the user is not shown a stuck or duplicated pending
   state upon return.
4. **Given** a Recommend conversation, **When** the user navigates away and back repeatedly (3+
   times) without sending anything new, **Then** state is preserved identically every time — no
   drift, no gradual loss of history.
5. **Given** a "Start styling" attempt has just failed and the error card with "Try again" is
   showing, **When** the user navigates away and back, **Then** the same error card is still
   showing and "Try again" still resumes from the same accumulated composer text.
6. **Given** the closet's contents changed while the user was away (e.g. items were added or
   removed on Closet), **When** the user returns to Recommend, **Then** the insufficient-closet
   gate and sparse-closet banner reflect the closet's current state, even though the
   conversation itself is unchanged.

---

### User Story 2 - "New chat" still starts fresh (Priority: P2)

A user done with a conversation taps "New chat" to start over.

**Why this priority**: The one deliberate reset path must keep working once persistence is
added — it's easy for a persistence fix to accidentally make this a no-op.

**Independent Test**: With an active conversation, tap "New chat," then navigate away and back.
The hero (empty) state is what's shown, not the old conversation.

**Acceptance Scenarios**:

1. **Given** an active conversation, **When** the user taps "New chat," **Then** the screen
   returns to the empty hero state and the "New chat" button itself becomes disabled again
   (matching its existing disabled-when-empty behavior).
2. **Given** the user tapped "New chat" and then navigates to another tab and back, **When** the
   Recommend screen remounts, **Then** it still shows the empty hero state — the reset is not
   itself undone by the persistence mechanism.

---

### User Story 3 - A real reload starts fresh (Priority: P2)

A user fully closes and reopens the installed app, or hard-reloads the browser tab.

**Why this priority**: The spec explicitly requires this as the other legitimate reset path,
distinguishing "in-app navigation" (must persist) from "a new session" (must not).

**Independent Test**: With an active conversation, perform a full page reload (not client-side
navigation). The hero state is shown, not the prior conversation.

**Acceptance Scenarios**:

1. **Given** an active conversation, **When** the browser tab is hard-reloaded or the installed
   PWA is fully closed and relaunched, **Then** Recommend shows the empty hero state.

---

### User Story 4 - Resuming a specific past thread via link still works (Priority: P3)

A user taps "Continue conversation" from Session detail (feature 011), landing on Recommend
with `?thread_id=` set.

**Why this priority**: Lower priority only because it is an existing, already-working path —
this story exists to guard it from regressing, not to build it new.

**Independent Test**: From Session detail, tap "Continue conversation" for a past session.
Recommend loads that session's prior turns. Navigate away and back — the resumed conversation
is still there, not re-fetched a second time or reset.

**Acceptance Scenarios**:

1. **Given** the user opens Recommend via a `?thread_id=` link for a session that is not the
   one currently active in memory (if any), **When** the screen loads, **Then** it fetches and
   displays that session's prior turns, replacing whatever conversation was previously active.
2. **Given** the user has just resumed a thread this way, **When** they navigate away and back
   to plain `/recommend` (no query param), **Then** the resumed conversation is still showing —
   the in-app navigation guarantee from User Story 1 applies here too.

---

### Edge Cases

- What happens if the user navigates away while a composer send (conversational turn) is
  in flight? → Covered by Acceptance Scenario 3 above: the in-flight call completes in the
  background and its result lands in the persisted state, applied whenever Recommend is next
  visible.
- What happens if the user taps "New chat" while a call is in flight? → The in-flight call may
  still complete and write into the (now-reset) persisted state; existing pre-feature behavior
  for this race is unaffected by this feature and is not newly introduced by it.
- What happens on the very first visit to Recommend in a session, with no prior conversation? →
  Unchanged: the hero (empty) state, exactly as today.
- What happens if the user has multiple browser tabs open to Recommend? → Out of scope for this
  feature; persistence is per-tab (an in-memory, single-tab mechanism), not synchronized across
  tabs. Each tab's conversation still fully resets on that tab's own reload.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST preserve the full in-progress Recommend conversation — sent
  messages, assistant replies, any generated outfits, the accumulated not-yet-styled composer
  text, the active thread identity, any in-flight request, and a visible "Start styling" failure
  (the error card and its "Try again" affordance) — across navigation to any other in-app
  destination and back, with no visible reset and no re-fetch-from-scratch.
- **FR-002**: The system MUST reset the Recommend conversation to the empty hero state when the
  user performs a real reload (closing and reopening the installed app, or a hard browser
  reload) — this is existing behavior (state does not survive a JS context restart) and MUST
  continue to hold; it is not a new behavior this feature must build, but it MUST NOT be
  broken by whatever mechanism satisfies FR-001.
- **FR-003**: The system MUST reset the Recommend conversation to the empty hero state when the
  user explicitly taps "New chat," and this reset MUST itself persist across subsequent in-app
  navigation (the empty state doesn't get "undone" by returning to a stale in-memory copy).
- **FR-004**: The system MUST continue to support opening Recommend with a `?thread_id=` link
  (the existing "Continue conversation" resume path) without regression: it fetches and displays
  that specific session's prior turns.
- **FR-005**: When a `?thread_id=` link names a thread that is different from whichever
  conversation is currently held in memory (including no conversation held), the system MUST
  replace the in-memory conversation with the fetched one rather than showing a stale one.
- **FR-006**: When a `?thread_id=` link names the same thread already held in memory, the system
  MUST NOT re-fetch or visibly reset it — the in-app navigation guarantee applies to this path
  too, per User Story 4.
- **FR-007**: A conversational turn or "Start styling" call that is in flight when the user
  navigates away MUST still be applied to the conversation when its response arrives, regardless
  of whether Recommend is the currently visible screen at that moment.
- **FR-008**: This feature MUST NOT change any backend behavior, API contract, or persistence
  mechanism (LangGraph checkpointer, `chat_history`) — the fix is confined to how the frontend
  holds and re-displays state it already has, not to how or whether the backend durably stores
  the conversation.
- **FR-009**: The Closet-readiness check (whether Recommend shows the chat vs. the insufficient-
  closet gate, and whether the sparse-closet banner shows) MUST be re-evaluated every time the
  user returns to Recommend, independent of the conversation-persistence mechanism — it is not
  itself preserved, so it always reflects the closet's current contents even if those changed
  while the user was on another screen.

### Key Entities

- **In-progress conversation state**: the client-held record of one active Recommend thread —
  its message list, accumulated not-yet-styled composer text, thread identity, and pending-call
  status. Today this exists only as one component's local state and dies with that component;
  this feature changes where it lives, not its shape or its source of truth (the backend remains
  authoritative for anything durable across a real reload).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user who navigates from Recommend to any other primary destination and back sees
  their conversation exactly as they left it, 100% of the time, with no empty-state flash.
- **SC-002**: "New chat" and a real app reload both continue to produce the empty hero state,
  100% of the time — the persistence fix introduces zero regressions to either existing reset
  path.
- **SC-003**: A styling reply or outfit result that arrives while the user is on a different
  screen is present, complete, and correctly placed in the conversation the next time the user
  returns to Recommend — it is never dropped, duplicated, or shown as stuck "pending."
- **SC-004**: The `?thread_id=` resume path (feature 011) continues to work with no observable
  change in behavior for a first-time resume, and gains the same navigate-away-and-back
  durability as an ordinary conversation.

## Assumptions

- "In-app navigation" means client-side route changes within the same loaded PWA/browser-tab
  session (e.g., Next.js client-side transitions between `/recommend`, `/closet`, `/outfits`,
  `/profile`, `/history`, etc.). It does not include a hard browser reload, closing and
  reopening the installed app, or opening a second tab — those are all "a real reload" per the
  issue's own framing, and FR-002 requires the reset to still happen there.
- Investigation (see the Assumptions note in this section and confirmed during planning) found
  no evidence the backend checkpointer/`chat_history` persistence itself is broken — the defect
  is confined to the frontend discarding its own in-memory state on component remount. Per the
  task's explicit scope boundary, if planning uncovers evidence to the contrary, that is
  reported separately rather than folded into this spec.
- Running a styling request in the background while the user is elsewhere and notifying them
  when it's ready (GitHub issue #53) is explicitly out of scope. This feature only guarantees
  that a response already in flight is not lost or orphaned if the user happens to navigate away
  before it resolves — it does not add any new background-execution, job-queue, or notification
  capability. The request is already initiated from Recommend before the user can navigate away
  from it in the current UI (there is no "kick off a request and immediately leave" flow today),
  so FR-007 is a safety net for an existing race, not new background functionality.
- Multi-tab synchronization is out of scope; each browser tab/PWA instance holds its own
  conversation state independently.
