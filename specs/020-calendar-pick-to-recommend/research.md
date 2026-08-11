# Phase 0 Research: Calendar Pick Reaches Recommend

## Why defect 2 is not the same fix as feature 019, despite the same symptom shape

**Task**: 019 solved "state is lost across an in-app navigation the Router Cache doesn't
remount for" using a module-level store persisted across unmount. Confirm whether that exact
mechanism applies to `RecommendCalendarContext`, or whether the differently-shaped bug needs a
differently-shaped fix, before writing any code.

**Finding**: different bug, same *category* of fix, different concrete mechanism.

- 019's bug: real, generated conversation state (`messages`, `pendingTexts`, `threadId`) lived
  in `useState` local to `RecommendChat`. On an in-app navigation that the Router Cache serves
  without a remount, nothing is lost technically — but on a navigation that the Router Cache
  *does* eventually evict and remount, the component starts over at its initial state and the
  real data is gone unless it lives somewhere that survives unmount. The fix: hold it in a
  module singleton, read via `useSyncExternalStore`.
- This defect's bug: `RecommendCalendarContext` fetches `/calendar/picked-event` in a
  `useEffect([])`. That effect runs whenever the component mounts. The problem is the inverse
  of 019's: this component does **not** need old data preserved across a remount it doesn't
  get — it needs **current server data on every arrival**, and the arrival in question (Calendar
  → pick → Recommend) is exactly the in-app navigation the issue names as one the Router Cache
  serves without remounting `/recommend`'s tree, so the mount-scoped effect simply never
  reruns and the component goes on showing whatever it last rendered (nothing, or a stale
  label), for as long as the cached segment survives.
- A store that only *persists* state (019's shape) does not fix this — persisting a stale
  fetch just makes the stale value durable. What's needed is the opposite: a store that gets
  **written to** at the moment the truth changes, independent of any component's mount
  timing.

**Decision**: `frontend/lib/calendar/pickedEventStore.ts`, a write-through module-level store
using the same `useSyncExternalStore` idiom as `recommendChatStore.ts` (`getState`,
`getServerSnapshot`, `subscribe`, a `setState`-shaped mutator), but with a different
responsibility: `set(event | null)` is called directly by `CalendarPage.handlePick` the
instant a pick's `PUT` response confirms success (defect 1's own now-checked result — no
second network call needed for the common case), and by anything else that changes the
server's picked-event record. `RecommendCalendarContext` subscribes via
`useSyncExternalStore` and renders whatever the store currently holds; it performs a GET only
to **hydrate** the store the first time this JS context sees it with no value yet (e.g. the
user opened `/recommend` directly, in a tab that never visited `/calendar`) — after that,
every update reaches every subscriber the instant it's written, with no dependency on which
component happens to be mounted or when.

**Alternatives considered**:

| Option | Rejected because |
|---|---|
| **Write-through store (chosen)** | Fixes the actual root cause — a fetch tied to a mount event that may not recur — rather than trying to force a remount or refetch to happen reliably. |
| Reuse `recommendChatStore.ts`'s exact shape (fetch-once, persist, never refetch) | Solves the wrong problem: this data must reflect Calendar's *current* truth, not be frozen at whatever it was first fetched. A persisted stale value is still stale. |
| Force a remount (e.g. a `key` on the route segment, or `router.refresh()`) | Depends on Next.js Router Cache internals this repo doesn't otherwise touch or test against, is more fragile to a framework version bump, and does nothing for the case where `/recommend` is reached without ever going through a fresh pick (still needs a real fetch path) — the write-through store needs that fetch path anyway, so it's strictly less code to have only one mechanism. |
| Poll `/calendar/picked-event` on an interval | Adds a recurring network cost for a value that changes only when the user takes an explicit action (picking an event) — there is always a specific moment the value changes, so polling trades correctness-by-luck for cost, when a write-through store gets correctness for free at the one moment it matters. |
| Re-fetch on `visibilitychange`/window focus | Narrower and less certain than a remount-independent store — doesn't fire on same-tab in-app navigation at all (the actual failure case named in the issue), only on tab-switch. |

## Where in `recommend.py` the picked-event read belongs

**Task**: confirm the seed happens once, on the right call, without duplicating work already
done elsewhere.

**Finding**: `POST /recommend/turns` is the only route that runs before a thread has any
state — `POST /recommend/messages`'s first-invoke branch already reads whatever
`graph.get_state(config).values` holds by the time it's called, so seeding earlier (in
`/recommend/turns`) is sufficient for both call paths; seeding again in `/recommend/messages`
would be redundant and would need its own "is this thread new" check duplicating the one
`/recommend/turns` already makes via `body.thread_id is None`.

**Decision**: `send_turn` (`recommend.py`), guarded by `body.thread_id is None` (the existing
signal for "this call is creating a brand-new thread," already used to generate a fresh
`thread_id`), reads the caller's picked event via a newly-injected
`SupabaseCalendarRepository` dependency and, when one exists, calls
`graph.update_state(config, {"location": event.location})` before `known_slots` is read.
`get_picked_event` returning `None` (no event picked) or a picked event with `location: None`
(the calendar event itself had no location) both no-op — nothing is written, matching how the
route already treats an absent extracted slot (`if value is not None`).

## Composer pre-fill: where the fresh-thread check lives, and what text to generate

**Decision**: `RecommendChat.tsx` (which already reads `chat.messages`/`chat.threadId` from
`recommendChatStore` and already computes `hasUserMessage`) computes the pre-fill text once,
from `pickedEventStore`'s current value, exactly when `!hasUserMessage` — the same condition
that already gates rendering `HeroState` — and passes it to `Composer` as `initialValue`.
`Composer` seeds its local `value` state from `initialValue` on first render only (a normal
`useState(initialValue)` — it does not re-sync on prop changes, matching the fact that once
the user starts editing, further store updates must not clobber their edit).

Text template: `` `${title}, ${relativeDayTime}` `` — reuses `formatEventTime` (already used
by `EventRow`) for the time half, so no second time-formatting convention is introduced.

## Confirmed: no OpenAPI contract change

**Task**: constitution VII/the task brief flag `schema.d.ts` regeneration as "likely." Checked
before assuming it.

**Finding**: not needed. `SendTurnRequest`/`SendTurnResponse` gain no field — the picked event
is read server-side, from the authenticated caller's own `picked_events` row, the same way
`GET /calendar/picked-event` already does. No route's request or response Pydantic model
changes shape. Verified by re-reading every model touched (`SendTurnRequest`,
`SendTurnResponse`, `CalendarEventView`, `PickedEventView`) — none gain, lose, or retype a
field. `schema.d.ts` is left untouched; regenerating it would be a no-op diff at best and a
false signal of an API change at worst.
