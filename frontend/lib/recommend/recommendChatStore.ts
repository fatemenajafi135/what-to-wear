import { apiClient } from "@/lib/api/client";
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

/** For `useSyncExternalStore`'s required third argument. This state is
 * client-only (FR-002/FR-008 — nothing here is ever meant to be server-
 * rendered), so a server prerender always sees the pristine empty
 * conversation — exactly what a fresh client load shows before hydration
 * takes over, never the live (possibly mutated) singleton. */
const serverSnapshot = initialState();
export function getServerSnapshot(): RecommendChatState {
  return serverSnapshot;
}

/** Registers `listener` to be called after any action changes state.
 * Returns the unsubscribe function. */
export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function setState(patch: Partial<RecommendChatState>) {
  state = { ...state, ...patch };
  notify();
}

/** "New chat" (FR-003) — also the test-isolation primitive: Vitest doesn't
 * reset a file's module graph between `it()` cases in the same file, so
 * tests call this in `beforeEach` to avoid leaking conversation state
 * across cases (research.md "Test isolation for a module singleton"). */
export function reset(): void {
  state = initialState();
  notify();
}

/** The `?thread_id=` resume path (FR-004/005) — replaces the conversation
 * wholesale. Callers only invoke this when `threadId` differs from
 * `getState().threadId` (FR-006: the same thread already held is an
 * in-app-navigation case, not a resume). */
export function hydrate(threadId: string, messages: ChatMessage[]): void {
  state = { ...initialState(), threadId, messages };
  notify();
}

/**
 * Every composer send (design-decisions.md §37/§47) — no retrieval, no
 * wardrobe, no generation. Mutates the singleton and notifies subscribers
 * directly rather than going through a component's setState, so a reply
 * that arrives after the user has navigated away from Recommend still
 * lands (FR-007) instead of silently no-oping against an unmounted
 * component.
 */
export async function sendTurn(text: string): Promise<void> {
  setState({
    messages: [...state.messages, { id: crypto.randomUUID(), role: "user", text }],
    pendingTexts: [...state.pendingTexts, text],
    turnPending: true,
  });

  const requestThreadId = state.threadId;
  const { data, error } = await apiClient.POST("/api/v1/recommend/turns", {
    body: { message: text, thread_id: requestThreadId },
  });

  if (error || !data) {
    // FR-010/SC-005: a genuine call/network failure leaves the
    // conversation usable — no bubble invented for it (research.md §9),
    // "Start styling" still works from whatever was already gathered.
    setState({ turnPending: false });
    return;
  }

  setState({
    turnPending: false,
    threadId: state.threadId ?? data.thread_id,
    messages: [
      ...state.messages,
      { id: crypto.randomUUID(), role: "assistant", replyText: data.reply_text, plain: true },
    ],
  });
}

/**
 * The sole trigger for outfit generation (design-decisions.md §37). Same
 * mount-independence rationale as `sendTurn` above — the response must
 * land in the persisted state whether or not `RecommendChat` is currently
 * subscribed to observe it.
 */
export async function startStyling(): Promise<void> {
  if (state.pendingTexts.length === 0) return;
  const message = state.pendingTexts.join(" ");
  const requestThreadId = state.threadId;
  setState({ startStyling: "pending" });

  const { data, error } = await apiClient.POST("/api/v1/recommend/messages", {
    body: { message, thread_id: requestThreadId },
  });

  if (error || !data) {
    setState({ startStyling: "error" });
    return;
  }

  setState({
    threadId: data.thread_id,
    messages: [
      ...state.messages,
      // The wrap-up renders as its own assistant message before the
      // outfits (design-decisions.md §49) — always present, never a
      // second LLM call.
      { id: crypto.randomUUID(), role: "assistant", replyText: data.wrap_up_text, plain: true },
      {
        id: crypto.randomUUID(),
        role: "assistant",
        outfits: data.outfits,
        replyText: data.reply_text,
      },
    ],
    pendingTexts: [],
    startStyling: "idle",
  });
}
