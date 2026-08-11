# Phase 0 Research: Recommend Chat Persists Across In-App Navigation

## Why this is a frontend-only defect (scope-boundary investigation)

**Task**: confirm, before planning any fix, that the backend persistence (LangGraph checkpointer
+ `chat_history`) is not itself broken — the task brief and FR-008 require stopping and flagging
this separately if it were.

**Finding**: it is not broken. Read end to end:

- `frontend/components/recommend/RecommendChat.tsx` holds `messages`, `pendingTexts`, `threadId`,
  `turnPending`, `startStyling` entirely in `useState` local to the component
  ([RecommendChat.tsx:52-57](../../frontend/components/recommend/RecommendChat.tsx)).
- `frontend/app/(app)/recommend/page.tsx` mounts a fresh `<RecommendChat>` on every render of the
  route. Next.js App Router unmounts the previous route's page tree and mounts the new one on
  client-side navigation between sibling routes under `app/(app)/layout.tsx` — only the layout
  itself (`TabBar`, `OfflineBanner`, `FocusOnNavigate`) survives navigation. `RecommendChat`'s
  local state is destroyed with it.
- Nothing re-fetches that state on remount for the ordinary (non-resume) case: `resumeThreadId`
  is only set when the URL carries `?thread_id=`, which plain in-app navigation to `/recommend`
  never does. So the component doesn't even attempt to recover the conversation — it starts at
  `messages: []`, `threadId: null`, i.e. the hero state, indistinguishable from a user who never
  started a conversation.
- The backend side this bypasses is fine: `docs/design-decisions.md` §37/§49/§50 describe a
  LangGraph checkpointer keyed by `thread_id` plus a durable `chat_history` table that the
  existing `?thread_id=` resume path (`GET /recommend/sessions/{id}`, feature 011) already reads
  from successfully. That path proves the backend record is intact and fetchable — the defect is
  that ordinary navigation never triggers a fetch or a state carry-over at all.

**Conclusion**: confirmed frontend-only, as the issue states. FR-008 (no backend change) is
adopted, not just as a constraint but as a supported design decision.

## Where to hold the conversation state so it survives unmount

**Decision**: a module-level external store (`frontend/lib/recommend/recommendChatStore.ts`) —
one singleton object outside the React tree, read reactively via `useSyncExternalStore`, mutated
by plain async functions that live in the same module.

**Rationale**:

- Module scope survives a component unmount/remount because it isn't attached to any component's
  lifecycle — it's just a JS object that lives as long as the page's JS context does. That JS
  context is exactly what a real reload (FR-002) tears down and rebuilds, so "resets only on a
  real reload or New chat" falls out of the mechanism for free rather than needing extra code to
  detect "was this a real reload."
- It survives navigation to *any* in-app route, not just the ones inside one particular layout
  group — important because FR-001 says "any other in-app destination," and this repo's route
  tree isn't guaranteed to keep every future destination inside `app/(app)/`.
- FR-007 (a response that arrives while the user is elsewhere must still land correctly) requires
  the code that applies a network response to run independent of whether a subscribing component
  currently exists. A `useState` setter silently no-ops (and warns) if called after unmount; a
  module-level mutation does not care whether anything is currently subscribed. This pushes the
  two network actions (send a conversational turn, Start styling) out of the component and into
  the store module as the actions that mutate it directly.
- No provider/wrapper component is needed anywhere — `RecommendChat` and `page.tsx` both simply
  import the same module and call `useSyncExternalStore(store.subscribe, store.getState)`. This
  is less code than the alternatives below, which is the tie-breaker under the constitution's
  "simplicity over abstraction" quality bar.

**Alternatives considered**:

| Option | Rejected because |
|---|---|
| React Context provided from `app/(app)/layout.tsx` | Only covers routes rendered inside that layout's `{children}`. If a future destination (e.g. a modal-style route) lives outside `(app)/`, navigating there and back would still lose state — the module singleton has no such boundary. Also requires a `Provider` wrapper component purely to hold a value a plain module can hold with zero JSX. |
| `sessionStorage` | Persists across a hard reload of the same tab (cleared only when the tab/window closes) — this would keep the conversation alive across the exact case FR-002 requires to reset it (a real reload). Using it correctly would need extra bookkeeping to distinguish "reload" from "in-app nav," which the module-singleton approach gets for free from the JS runtime's own lifecycle. |
| `localStorage` | Same problem as `sessionStorage`, worse — survives even a full app close, directly contradicting FR-002. |
| Keep `useState`, but re-fetch the thread's transcript from the backend on every remount (treat every return to Recommend like the existing `?thread_id=` resume path) | Turns a client-side navigation into a network round-trip every time, which is exactly the "re-fetches and re-renders from scratch" symptom the issue reports as the feel of loss (a visible flash/skeleton), even if the data underneath is correct. It would also not solve FR-007 (an in-flight call still needs somewhere to land its result if the component is unmounted when it resolves). |

## Where "New chat" and readiness now live

**Decision**: "New chat" becomes a direct `recommendChatStore.reset()` call from `page.tsx`
(reading `hasUserMessage` from the same store) instead of the current
`forwardRef`/`useImperativeHandle` handle passed down from `page.tsx` into `RecommendChat`.
Closet-readiness (`GET /recommend/readiness`) stays exactly where it is today — local
`useState`/`useEffect` inside `RecommendChat`, refetched on every mount.

**Rationale**: once both `page.tsx` and `RecommendChat` can read the same store directly, the
ref/callback indirection that only ever existed to let `page.tsx` reach into `RecommendChat`'s
local state has no remaining purpose — removing it is a simplification enabled by, not required
by, the persistence fix. Readiness is explicitly excluded from the store per the
`/speckit-clarify` decision recorded in spec.md (FR-009): it must reflect the closet's *current*
contents on every return, which is the opposite of "persist across navigation," so mixing it into
the same store would require carving out an exception rather than just leaving it alone.

## Test isolation for a module singleton

**Decision**: `recommendChatStore` exports its existing `reset()` (the same function "New chat"
calls) for tests to call in `beforeEach`. No test-only production code is added.

**Rationale**: Vitest does not reset a file's module graph between individual `it()` cases within
the same test file (only test files themselves run isolated) — so without an explicit reset, the
singleton would leak conversation state from one test into the next, corrupting assertions like
"Start styling is hidden in the hero state (0 messages)" if an earlier test in the same file
already sent a message. `reset()` already exists as production behavior (it's what "New chat"
does), so calling it from `beforeEach` in `RecommendChat.test.tsx` and `page.test.tsx` reuses
real code rather than adding a parallel test-only reset path.

## `?thread_id=` resume path vs. the persisted store (FR-004/005/006)

**Decision**: `page.tsx` keeps its existing `GET /recommend/sessions/{id}` fetch-on-mount effect,
gated by comparing the URL's `thread_id` against the store's *current* `threadId` before deciding
to fetch:

- URL `thread_id` differs from the store's current thread (including the store being empty) →
  fetch that session's turns and call `recommendChatStore.hydrate(threadId, messages)`, replacing
  whatever was there (FR-005).
- URL `thread_id` matches the store's current thread → skip the fetch entirely; the store already
  holds it, and the in-app-navigation guarantee (User Story 1) applies here exactly as it does to
  an unprefixed `/recommend` visit (FR-006).

**Rationale**: this is the minimum change that satisfies FR-004/005/006 — the comparison-and-skip
logic didn't exist before because there was no persisted store to compare against; the fetch
itself, and the shape of what it fetches, is unchanged.
