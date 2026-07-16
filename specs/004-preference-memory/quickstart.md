# Quickstart: Preference Memory

Validates the feature end-to-end against a running backend. Mirrors
Feature 001/003's quickstart pattern (real Supabase DB, real JWT, no mocks).

## Prerequisites

- `backend/.env` filled in (`DATABASE_URL`, `SUPABASE_URL`, gateway keys —
  see root `CLAUDE.md`).
- Migration `0003_add_suggestion_feedback.py` applied:
  `uv run alembic upgrade head`.
- A signed-in test user with a non-empty closet (the eval baseline user
  seeded via `uv run python -m whattowear.crud seed-eval-baseline` works,
  or any user who has added items via `POST /wardrobe/items`).
- Backend running: `uv run uvicorn whattowear.api:app --reload`.

## 1. Get a suggestion, then react to it

```bash
TOKEN="<supabase JWT for the test user>"

curl -s -X POST http://localhost:8000/recommend \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"request": "something for a casual coffee date"}' | tee /tmp/rec.json

ITEM_IDS=$(jq -c '.outfits[0].items' /tmp/rec.json)

curl -s -X POST http://localhost:8000/preferences/feedback \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d "{\"verdict\": \"rejected\", \"reason\": \"too formal\", \"item_ids\": $ITEM_IDS}"
```

**Expect**: `201` with the feedback echoed back, `id` present.

## 2. Reacting again to the same outfit replaces, not accumulates

Re-run the same `POST /preferences/feedback` call with `"verdict": "liked"`
against the identical `item_ids`.

**Expect**: `201`, same logical record (verify by re-fetching — no way to
list raw feedback in this feature's contract, but `GET /preferences`
below reflects only the latest verdict per outfit — a color from an outfit
reacted-to-then-changed-to-liked must not count toward a rejected-color
signal).

## 3. Build a pattern, then confirm the profile

Repeat step 1 (a fresh `/recommend` call each time so outfits vary) with
`"verdict": "rejected"` at least 3 times for outfits that share a color —
easiest with a closet where one color dominates, or by rejecting until the
same color recurs 3 times.

```bash
curl -s http://localhost:8000/preferences -H "Authorization: Bearer $TOKEN"
```

**Persistence check (FR-012/SC-005)**: stop the `uvicorn` process (Ctrl-C)
and start it again (`uv run uvicorn whattowear.api:app --reload`), then
re-run the `GET /preferences` call above with the same token. Expect the
identical signals to still be present — this is the concrete difference
from the pre-Feature-004 behavior, where everything lived in an
in-process `InMemoryStore` and a restart silently wiped it.

**Expect**: `has_feedback: true`, and a `signals` entry with
`key` starting `color:` once that color has been net-rejected
`>= MIN_SIGNAL_COUNT` (3) times, in plain language — no raw hex/internal
ids in the `summary` text (FR-007).

## 4. New suggestions reflect the learned signal (US2)

```bash
curl -s -X POST http://localhost:8000/recommend \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"request": "something for a casual coffee date"}'
```

**Expect**: the rejected color appears measurably less often across
several repeated calls than in step 1, before any feedback existed
(SC-002) — this is a soft, statistical effect (LLM-in-the-loop
generation), not a hard filter; compare frequency across ~5 calls, not a
single call.

## 5. Remove one signal, confirm the rest survive

If the profile from step 3 has more than one signal (repeat step 3 for a
second color/category to get two), pick one:

```bash
curl -s -X DELETE "http://localhost:8000/preferences/signals/color%3A%231b2a4a" \
  -H "Authorization: Bearer $TOKEN" -w '%{http_code}\n'

curl -s http://localhost:8000/preferences -H "Authorization: Bearer $TOKEN"
```

**Expect**: `204`, and the removed signal is gone from `GET /preferences`
while any other signal from step 3 remains (FR-009, US4 AC1).

## 6. Clear the entire profile

```bash
curl -s -X DELETE http://localhost:8000/preferences \
  -H "Authorization: Bearer $TOKEN" -w '%{http_code}\n'

curl -s http://localhost:8000/preferences -H "Authorization: Bearer $TOKEN"
```

**Expect**: `204`, then `{"has_feedback": false, "signals": []}` — and a
follow-up `/recommend` call behaves as it did in step 1, before any
feedback existed (SC-004).

## 7. Isolation (FR-011)

Repeat steps 1/3 with a second user's token. Confirm `GET /preferences`
for user B never shows user A's signals, and `DELETE
/preferences/signals/{key}` with user B's token cannot affect user A's
profile (matches `/wardrobe/items`'s existing per-user isolation test
pattern in `backend/tests/integration/`).

## 8. New user, no feedback (SC-006)

With a brand-new user (empty feedback history):

```bash
curl -s http://localhost:8000/preferences -H "Authorization: Bearer $TOKEN"
```

**Expect**: `{"has_feedback": false, "signals": []}`, and `/recommend`
succeeds normally with no delay/degradation/error (`profile_note()`
returns `None`, generator behaves exactly as it does today).

## 9. Frontend

```bash
cd frontend && npm run fetch:openapi && npm run typecheck && npm run build
```

Then, with `uvicorn` running: sign in, get a suggestion, use the new
reaction affordance on `SuggestionResult.tsx` to like/reject an outfit,
visit the new `/preferences` route, confirm the plain-language summary
renders and a "nothing learned yet" state shows for a fresh user.

## Automated equivalents

- `backend/tests/unit/test_preferences.py` — `derive_signals()` threshold
  logic (net-count, formality drift, dismissal filtering) with hand-built
  data, no DB.
- `backend/tests/integration/test_preferences_api.py` — all 4 endpoints
  against the live Supabase DB (rollback-transaction fixture): record,
  upsert-replace, view, remove-one, clear-all, and cross-user isolation.
