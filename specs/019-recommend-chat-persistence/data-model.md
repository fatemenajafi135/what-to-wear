# Phase 1 Data Model: Recommend Chat Persists Across In-App Navigation

No database entities. This feature touches client-held, in-memory conversation state only —
FR-008 forbids any backend or persistence-layer change, so nothing here is durable across a real
reload; the backend's own durable shape (LangGraph checkpoint, `chat_history` rows) is unchanged
and out of scope.

## `RecommendChatState` (client-only, module singleton)

The shape held by `frontend/lib/recommend/recommendChatStore.ts`, replacing what
`RecommendChat.tsx` currently holds as five separate `useState` calls. Field-for-field the same
data, just relocated:

| Field | Type | Source today | Notes |
|---|---|---|---|
| `messages` | `ChatMessage[]` | `RecommendChat`'s `messages` state | Unchanged shape (`components/recommend/ChatMessageList.tsx`'s existing `ChatMessage` type). |
| `pendingTexts` | `string[]` | `RecommendChat`'s `pendingTexts` state | Accumulated composer sends not yet folded into a "Start styling" call (design-decisions.md §37/§49's mechanism). |
| `threadId` | `string \| null` | `RecommendChat`'s `threadId` state | Identity of the active LangGraph thread, echoed on every backend call once assigned. |
| `turnPending` | `boolean` | `RecommendChat`'s `turnPending` state | True while a conversational-turn POST is in flight. |
| `startStyling` | `"idle" \| "pending" \| "error"` | `RecommendChat`'s `startStyling` state | Distinct from `turnPending` per design-decisions.md §37 — its own bubble/state. |

Explicitly **not** part of this state (per FR-009, the `/speckit-clarify` decision, and the
Assumptions in spec.md):

- Closet readiness (`ready`/`sparse`/`missing`) — stays local to `RecommendChat`, refetched on
  every mount.
- The calendar-context picked event (`RecommendCalendarContext`) — already its own independent
  concern, unaffected by this feature.
- The composer's currently-typed-but-unsent draft text — not "conversation," resets on remount
  today and continues to; nothing in the issue or spec asks for it to survive.

## State transitions

Unchanged from current behavior — this feature relocates where the state lives, not what causes
it to change:

- `sendTurn(text)`: appends a user message, appends `text` to `pendingTexts`, sets
  `turnPending: true`; on response, sets `turnPending: false` and appends an assistant message
  (or leaves `pendingTexts`/`messages` as-is on error, matching the existing "no bubble invented
  for a failed turn" behavior).
- `startStyling()`: sets `startStyling: "pending"`; on success, appends the wrap-up and
  outfit-bearing assistant messages, clears `pendingTexts`, sets `startStyling: "idle"`; on
  failure, sets `startStyling: "error"`.
- `hydrate(threadId, messages)`: replaces `messages` and `threadId` wholesale, resets
  `pendingTexts`/`turnPending`/`startStyling` to their empty/idle defaults — used only by the
  `?thread_id=` resume path when the URL names a thread different from what's already held
  (FR-005).
- `reset()`: returns every field to its empty/idle default — "New chat" (FR-003), and also the
  test-isolation hook (Research.md's "Test isolation for a module singleton").

No new transition is introduced. `hydrate` and `reset` both already exist conceptually today
(the resume-props path and the imperative `newChat()` handle, respectively); this feature gives
them a stable home that survives remounts instead of one that doesn't.
