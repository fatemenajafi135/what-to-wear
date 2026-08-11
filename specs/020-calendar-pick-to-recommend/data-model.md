# Phase 1 Data Model: Calendar Pick Reaches Recommend

No database schema change. This feature reads one existing table
(`picked_events`, migration `0004`, via the existing `SupabaseCalendarRepository`) from one
additional call site and writes to the existing LangGraph checkpoint (no new column, no new
table).

## `PickedEventContext` (client-only, module singleton)

The shape held by `frontend/lib/calendar/pickedEventStore.ts` — a write-through cache of the
server's `picked_events` row for the signed-in user, not a new entity.

| Field | Type | Source | Notes |
|---|---|---|---|
| `status` | `"unknown" \| "loaded"` | Internal | `"unknown"` until either the one hydration GET resolves or `set()` is called for the first time — lets subscribers distinguish "haven't checked yet" from "checked, nothing picked" (matters for the composer pre-fill, which must not fire on stale/unknown data). |
| `event` | `{ google_event_id: string; title: string; start: string; location: string \| null } \| null` | `PUT /calendar/picked-event`'s own response (write-through) or `GET /calendar/picked-event` (hydration only) | Mirrors the existing `CalendarEventView` shape from `frontend/lib/api/schema.d.ts` — no new client-side type, just where it's held. |

State transitions:

- `hydrate()`: called once by the first `RecommendCalendarContext` (or any future subscriber)
  to observe `status === "unknown"`. Issues the existing `GET /calendar/picked-event` call and
  writes the result. A second/third subscriber mounting while `status` is already `"loaded"`
  triggers no fetch.
- `set(event | null)`: called by `CalendarPage.handlePick` the instant a pick's `PUT` response
  confirms success — writes the confirmed event directly, `status: "loaded"`, no fetch
  involved. Also the hook a future "disconnect calendar" or "unpick" affordance would call
  with `null` (not built by this feature — see spec.md Edge Cases — but the store's shape
  doesn't foreclose it).

## Conversation slot state (existing LangGraph checkpoint) — one new writer, no new field

`GraphState.location: str | None` already exists (`pipeline/graph.py`). This feature adds one
more code path that writes it: `POST /recommend/turns`, on a thread's first turn only, seeded
from the caller's `picked_events.location` when present. No new key, no new type — the same
field every other conversational-turn extraction already writes via
`graph.update_state(config, updates)`.

## Composer pre-fill text (derived, not stored)

Computed at render time from `pickedEventStore`'s current `event` — not persisted anywhere.
`` `${event.title}, ${formatEventTime(event.start)}` ``, using the existing
`lib/calendar/formatEventTime.ts` the Calendar screen's own `EventRow` already uses.
