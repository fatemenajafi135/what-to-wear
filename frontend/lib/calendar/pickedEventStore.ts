import { apiClient } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

export type CalendarEventView = components["schemas"]["CalendarEventView"];

/**
 * specs/020-calendar-pick-to-recommend, contracts/picked-event-store.md — the Recommend
 * screen's picked-event context lives here, outside the React tree, same
 * `useSyncExternalStore` idiom as `lib/recommend/recommendChatStore.ts` (feature 019). The
 * two stores solve different problems, though: recommendChatStore PERSISTS real generated
 * conversation state across an unmount the Router Cache doesn't give it. This store's job is
 * the opposite — the value must always reflect Calendar's CURRENT server truth, not be frozen
 * at whatever was first fetched. So this is a WRITE-THROUGH cache: `set()` is called with an
 * already-confirmed server response the instant one exists (`CalendarPage.handlePick`'s
 * successful `PUT`), and `hydrate()` only ever fills the store the one time this JS context
 * has never checked — it never re-fetches just because a new subscriber mounted. That's what
 * fixes the staleness at its root: a subscriber sees the truth the moment it's written,
 * independent of whether the component holding it happens to remount (research.md's "Why
 * defect 2 is not the same fix as feature 019").
 */
export interface PickedEventState {
  status: "unknown" | "loaded";
  event: CalendarEventView | null;
}

function initialState(): PickedEventState {
  return { status: "unknown", event: null };
}

let state: PickedEventState = initialState();
const listeners = new Set<() => void>();
let hydrating: Promise<void> | null = null;

function notify() {
  for (const listener of listeners) listener();
}

/** Reactive read — pairs with React's `useSyncExternalStore`. Never triggers a fetch; always
 * returns the current snapshot synchronously. */
export function getState(): PickedEventState {
  return state;
}

/** For `useSyncExternalStore`'s required third argument — a fresh client before hydration
 * (or a server prerender) sees "unknown," never a live/possibly-stale singleton. */
const serverSnapshot = initialState();
export function getServerSnapshot(): PickedEventState {
  return serverSnapshot;
}

/** Registers `listener` to be called after any action changes state. Returns the unsubscribe
 * function. */
export function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Write-through — called with an already-confirmed server response, never optimistically.
 * `event: null` clears the pick (e.g. a future "disconnect calendar" flow). */
export function set(event: CalendarEventView | null): void {
  state = { status: "loaded", event };
  notify();
}

/** Fills the store the one time this JS context has never checked. A no-op once `status` is
 * already `"loaded"` — later updates only ever come from `set()`, matching the fact that
 * nothing about the picked event changes on its own; it changes only when something in this
 * app writes a new pick. Concurrent callers share the one in-flight request. */
export function hydrate(): void {
  if (state.status !== "unknown" || hydrating !== null) return;
  hydrating = apiClient
    .GET("/api/v1/calendar/picked-event")
    .then(({ data }) => {
      set(data?.picked && data.event ? data.event : null);
    })
    .finally(() => {
      hydrating = null;
    });
}

/** Test-isolation primitive — mirrors `recommendChatStore.reset()`: Vitest doesn't reset a
 * file's module graph between `it()` cases in the same file. */
export function reset(): void {
  state = initialState();
  hydrating = null;
  notify();
}
