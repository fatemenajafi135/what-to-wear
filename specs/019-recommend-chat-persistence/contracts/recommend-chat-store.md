# Contract: `recommendChatStore`

No backend/API contract changes in this feature (FR-008). The interface this feature actually
introduces is internal to the frontend: the public surface of the new store module, which
`RecommendChat.tsx`, `page.tsx`, and their tests all code against. Documented here because it's
the seam every consumer and every test crosses.

**Module**: `frontend/lib/recommend/recommendChatStore.ts`

```ts
export interface RecommendChatState {
  messages: ChatMessage[]; // components/recommend/ChatMessageList.tsx's existing type
  pendingTexts: string[];
  threadId: string | null;
  turnPending: boolean;
  startStyling: "idle" | "pending" | "error";
}

// Reactive read — pairs with React's useSyncExternalStore.
export function getState(): RecommendChatState;
export function subscribe(listener: () => void): () => void; // returns unsubscribe

// Actions. Each mutates the singleton and notifies subscribers itself; none
// depend on a component being mounted to observe the result (FR-007).
export function sendTurn(text: string): Promise<void>;
export function startStyling(): Promise<void>;
export function hydrate(threadId: string, messages: ChatMessage[]): void;
export function reset(): void;
```

## Behavioral guarantees

- `getState()` always returns the current snapshot synchronously; it never triggers a fetch.
- `subscribe(listener)` fires `listener` after any action changes state — including when the
  component that started an async action (`sendTurn`/`startStyling`) is no longer mounted to
  receive it directly; a *later* subscriber (a remounted `RecommendChat`) sees the already-applied
  result via its next `getState()` call, made when it re-subscribes.
- `sendTurn`/`startStyling` are safe to call with no mounted subscriber at all (e.g. immediately
  before a synchronous navigation) — they run to completion and apply their result regardless.
- `hydrate` and `reset` are synchronous and take effect before they return.
- `reset()` is the single reset primitive — both "New chat" (production) and test setup
  (`beforeEach`) call the same function, per research.md's "Test isolation" decision.

## Consumers

| Consumer | Uses |
|---|---|
| `frontend/components/recommend/RecommendChat.tsx` | `useSyncExternalStore(subscribe, getState)` for render; calls `sendTurn`/`startStyling` from its event handlers. No longer owns `useState` for any of `RecommendChatState`'s fields. |
| `frontend/app/(app)/recommend/page.tsx` | Reads `getState().messages` (for `hasUserMessage`, replacing the `onHasUserMessageChange` callback prop) and calls `reset()` directly from the "New chat" `IconButton` (replacing `chatRef.current?.newChat()`); calls `hydrate()` from its existing `?thread_id=` resume effect, gated by comparing the URL's `thread_id` to `getState().threadId` first. |
| `frontend/components/recommend/RecommendChat.test.tsx`, `frontend/app/(app)/recommend/page.test.tsx` | Call `reset()` in `beforeEach` for test isolation (research.md). |

## What is explicitly outside this contract

- Closet readiness (`GET /recommend/readiness`) — stays `RecommendChat`-local `useState`, not a
  store action (FR-009).
- Any backend endpoint or response shape — unchanged (FR-008).
