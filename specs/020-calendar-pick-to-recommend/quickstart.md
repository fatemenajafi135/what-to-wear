# Quickstart: Calendar Pick Reaches Recommend

## Prerequisites

- Local stack running per the repo root `CLAUDE.md`/`quickstart.md`: `backend/` `uv sync` +
  `uv run uvicorn whattowear.main:app --reload`, `infra/` `docker compose up -d` (Supabase +
  Qdrant), `frontend/` `npm run dev`.
- A signed-in test user with a wardrobe past the readiness floor (`wtw_wardrobe_min_items`) —
  reuse whatever fixture user prior features' manual passes used.
- **No live Google OAuth required to validate this feature's own logic** — the picked-event
  record this feature reads/writes is reachable directly via
  `PUT /api/v1/calendar/picked-event`, which only needs a signed-in session, not a completed
  Google consent round-trip. A real OAuth connection is only needed to prove `GET
  /calendar/events` itself still works, which this feature does not change.

## Scenario A — defect 1: pick → navigate

1. Seed a picked event: `PUT /api/v1/calendar/picked-event` with a body like
   `{"google_event_id": "qs-1", "title": "Dinner with Ana", "start": "<a near-future ISO
   timestamp>", "location": "Tanto"}` — OR, with a real/mocked Google Calendar connection, use
   the Calendar screen's own event list and tap a row.
2. **Expected**: on success, the browser lands on `/recommend` with no manual navigation.
3. Repeat with the backend temporarily returning a non-2xx for the PUT (e.g. stop the backend
   mid-request, or point the client at an invalid URL for one request) — **expected**: no
   navigation, rows remain tappable, a `Banner` error shows.

## Scenario B — defect 2: current context on arrival

1. With an event already picked (Scenario A), open `/recommend`, then click to `/closet` (or
   any other tab), then back to `/recommend` via the tab bar (in-app navigation, not a reload).
2. **Expected**: the calendar-context line already reads "Styling for {title} · Change" on
   the very first paint after returning — no flash of "Style for an event from calendar," no
   delay.
3. Pick a *different* event, land on `/recommend` per Scenario A — **expected**: the label
   reflects the new event immediately, not the previous one.

## Scenario C — defect 3: the conversation knows what the calendar knows

1. Ensure the active thread is fresh: either a first-ever visit, or tap "New chat" first.
2. Pick an event with a `location` set (Scenario A) and land on `/recommend`.
3. **Expected**: the Composer's input already contains editable text like "Dinner with Ana,
   Fri 8:00 PM" — nothing has been sent yet.
4. Send that text as-is (or edited). **Expected**: the assistant's reply does not ask "where
   will this be?" / "what's the location?" — it may ask about mood/formality if unclear, but
   not location.
5. Tap "Start styling." **Expected**: the request reaches the pipeline with the event's
   location already populated in the assembled `Context` (verifiable via LangSmith trace, or
   by checking the reply/outfits reference weather-appropriate items for that location's
   actual current conditions).
6. Contradiction check: pick an event with `location: "Tanto"`, then before sending anything
   else, edit the pre-filled Composer text to say "actually let's say it's at the beach" and
   send. **Expected**: the location the conversation carries forward is the one the user just
   stated, not "Tanto" — verify via a second message asking "where am I going again?" or by
   inspecting `SendTurnResponse.location` on the next turn.

## Automated coverage (see tasks.md)

- `frontend/app/(app)/calendar/page.test.tsx` — success/failure/in-flight `handlePick` cases.
- `frontend/lib/calendar/pickedEventStore.test.ts` — hydrate-once, write-through `set`,
  server-snapshot shape.
- `frontend/components/calendar/RecommendCalendarContext.test.tsx` — renders from the store,
  not from its own fetch.
- `backend/tests/.../test_recommend_turns_calendar_seed.py` (exact path decided in tasks.md) —
  seeds `location` on a fresh thread only, leaves it alone on a continuing thread, no-ops when
  no event is picked or the picked event has no location.
