# Quickstart: Closet (read)

Environment setup is covered by `notes/run-locally.md`. This file only adds the
closet-specific validation once that baseline is running.

## Prerequisites

```bash
cd infra && npx supabase start   # leave running
cd infra && npx supabase db reset   # replays every migration from empty, 0002 included
```

## Backend — fast checks, no database

```bash
cd backend
uv run pytest tests/unit -v
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run lint-imports
```

Expected: 459+ passing (this feature adds new unit tests; it must not remove or break any of
the existing 459).

## Backend — RLS isolation proof (needs a running local Supabase)

```bash
uv run pytest tests/integration/test_wardrobe_rls.py -v
```

Connects directly to Postgres (port 54322) as the `authenticator` role — not through the
app's own bypass-privileged pooler connection — `SET ROLE authenticated`, sets
`request.jwt.claim.sub` to each of two seeded users in turn, and asserts a raw, unfiltered
`SELECT * FROM wardrobe_items` returns only that user's rows. See `research.md` §1–2 for why
this has to run outside the app's own connection to mean anything.

## Backend — repository and routes (needs a running local Supabase)

```bash
uv run pytest tests/integration/test_closet_routes.py tests/unit/test_supabase_closet_repository.py -v
uv run uvicorn whattowear.main:app --reload
```

```bash
# 401 — no token
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/v1/closet/items   # expect 401

# 200 — real token (see specs/003-auth/quickstart.md for how to obtain one)
curl -s -H "Authorization: Bearer $TOKEN" localhost:8000/api/v1/closet/items | jq .

# 404 — someone else's item id, or a random uuid
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $TOKEN" \
  localhost:8000/api/v1/closet/items/00000000-0000-0000-0000-000000000000   # expect 404
```

## Frontend — generate types, then run

```bash
cd backend && uv run uvicorn whattowear.main:app --reload &     # needs to be running
cd frontend && npm run generate:api-types                       # writes lib/api/schema.d.ts
npm ci && npm run dev
```

1. **Empty, first run**: a brand-new signed-up user visits `/closet` — confirm
   `closet.empty.first_run.body`/`.cta`, not the filtered variant.
2. **Populated grid**: insert a few rows for the signed-in user directly in Supabase Studio
   (`localhost:54323`) across at least two category groups (include one `full_body` item),
   reload `/closet` — confirm the item count subtitle, the grid at 2/3/4 columns
   (320/768/1024px), and that the `full_body` item appears under the **Bottoms** chip.
3. **Empty-filtered**: select a category chip with zero matching items — confirm
   `closet.empty.filtered.body`/`.cta`, distinct copy from step 1, and that "Clear filter"
   restores the full grid.
4. **Item detail**: open an item — confirm Name/Category/Group/Fabric/Colour/Notes render as
   label/value pairs, the photo block shows the diagonal-stripe placeholder, and the header's
   overflow (dots) trigger is present (its sheet is feature 005's — confirm this feature
   leaves it either absent or empty, per whichever the implementation report states).
5. **Desktop two-pane**: at ≥1024px, confirm the grid becomes the wide list pane beside a
   detail pane showing "Select an item from your closet to see its details." until an item is
   clicked.
6. **Error**: temporarily stop the backend (or block the request in devtools), reload
   `/closet` — confirm `closet.error.body`/`.cta` with a working Retry.
7. **Offline**: go offline in devtools (Network tab), reload/interact with `/closet` — confirm
   the global offline banner appears and the screen does **not** also show its own error copy
   for the same failure (design-system §6's precedence rule).
8. Repeat 1–7 in dark mode (OS-level toggle; the app follows without reload).

## Two-user isolation, end to end (manual, complements the automated RLS test)

1. Sign up as user A, add rows for A only (via Studio).
2. Sign up as user B in a second browser profile/incognito window.
3. Confirm B's `/closet` shows zero of A's items, and `GET /api/v1/closet/items/{A's item
   id}` as B returns 404.
