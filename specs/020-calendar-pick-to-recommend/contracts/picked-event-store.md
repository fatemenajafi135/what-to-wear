# Contract: `lib/calendar/pickedEventStore.ts`

Module-level, client-only. No network contract of its own beyond the two existing REST calls
it wraps (`GET`/`PUT /api/v1/calendar/picked-event`, unchanged, already generated in
`frontend/lib/api/schema.d.ts`).

## Exports

```ts
export interface PickedEventState {
  status: "unknown" | "loaded";
  event: CalendarEventView | null; // schema.d.ts's existing type, re-exported not redefined
}

export function getState(): PickedEventState;
export function getServerSnapshot(): PickedEventState; // status: "unknown", event: null — matches a fresh client before hydration
export function subscribe(listener: () => void): () => void;

/** Idempotent no-op if status is already "loaded" or a hydrate is already in flight. */
export function hydrate(): void;

/** Write-through — called with the confirmed server response, never optimistically. */
export function set(event: CalendarEventView | null): void;
```

## Behavioral contract

1. `getState()` before any `hydrate()`/`set()` call in this JS context returns
   `{ status: "unknown", event: null }`.
2. `hydrate()` performs exactly one `GET /api/v1/calendar/picked-event` the first time it's
   called while `status === "unknown"`; concurrent callers (e.g. two components mounting in
   the same tick) share the one in-flight request rather than issuing a second.
3. `set(event)` synchronously updates `status: "loaded"` and notifies subscribers — no
   network call.
4. Once `status === "loaded"`, `hydrate()` is a no-op — the store is not re-fetched just
   because a new subscriber mounted. Only `set()` (a confirmed write elsewhere in the app)
   changes `event` after that point.
5. Consumers read via `useSyncExternalStore(subscribe, getState, getServerSnapshot)` — same
   idiom as `recommendChatStore`.

## Call sites (this feature)

| Caller | Action |
|---|---|
| `RecommendCalendarContext.tsx` | Subscribes; calls `hydrate()` once on first render if `status === "unknown"`; renders "Style for an event from calendar" when `event === null`, "Styling for {event.title} · Change" when set — unchanged copy, unchanged markup, only the data source changes. |
| `RecommendChat.tsx` | Reads `getState().event` (via the same subscription) to compute the Composer pre-fill text, gated on `!hasUserMessage`. |
| `app/(app)/calendar/page.tsx` (`handlePick`) | Calls `set(response.data.event)` the instant the `PUT` resolves successfully — see `contracts/calendar-pick-flow.md`. |
