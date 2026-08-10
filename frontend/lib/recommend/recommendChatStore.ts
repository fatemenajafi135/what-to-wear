import type { ChatMessage } from "@/components/recommend/ChatMessageList";

/**
 * specs/019-recommend-chat-persistence — the Recommend screen's conversation
 * lives here, outside the React tree, instead of in `RecommendChat`'s local
 * `useState`. A module-scoped singleton survives a component unmount/remount
 * (what in-app navigation does to a page's component tree) but not a real
 * reload (what tears down the whole JS context) — that split is exactly
 * FR-001/FR-002's persist-vs-reset boundary, and it falls out of where this
 * state lives rather than needing code to detect "was this a reload."
 *
 * The two network actions (`sendTurn`, `startStyling`) live in this module
 * too, not in the component, so a response that arrives after the user has
 * navigated away still lands correctly (FR-007) — a `useState` setter would
 * silently no-op on an unmounted component, but a module-level mutation
 * doesn't care whether anything is currently subscribed.
 *
 * See specs/019-recommend-chat-persistence/{research,data-model}.md and
 * contracts/recommend-chat-store.md for the full design record.
 */

/** Start-styling request status only — a conversational turn's own
 * in-flight state is tracked separately (`turnPending`) since the two are
 * distinct states with distinct bubbles (design-decisions.md §37). */
export type StartStylingStatus = "idle" | "pending" | "error";

export interface RecommendChatState {
  messages: ChatMessage[];
  /** Composer sends accumulated since the last "Start styling" tap
   * (design-decisions.md §37/§49's mechanism) — still raw text, since
   * "Start styling" needs it as its fallback/refinement signal. */
  pendingTexts: string[];
  threadId: string | null;
  turnPending: boolean;
  startStyling: StartStylingStatus;
}

function initialState(): RecommendChatState {
  return {
    messages: [],
    pendingTexts: [],
    threadId: null,
    turnPending: false,
    startStyling: "idle",
  };
}

let state: RecommendChatState = initialState();
const listeners = new Set<() => void>();

function notify() {
  for (const listener of listeners) listener();
}

/** Reactive read — pairs with React's `useSyncExternalStore`. Never
 * triggers a fetch; always returns the current snapshot synchronously. */
export function getState(): RecommendChatState {
  return state;
}

/** Registers `listener` to be called after any action changes state.
 * Returns the unsubscribe function. */
export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
