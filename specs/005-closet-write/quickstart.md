# Quickstart: Closet (write)

## Prerequisites

```bash
cd infra && npx supabase start          # local Postgres/Auth/Storage
cd ../backend && uv sync
cd ../frontend && npm ci
```

## Apply the migration

```bash
cd infra && npx supabase db reset       # applies 0001-0005 from empty
```

Confirms `wardrobe_items.favorite` and `item_wears` exist, RLS is enabled on both, and the
`authenticated` role has the expected grants (§9's definition-of-done item 1).

## Run the backend

```bash
cd backend && uv run uvicorn whattowear.main:app --reload
```

## Regenerate frontend API types

```bash
cd frontend && npm run generate:api-types   # backend must be running (previous step)
```

## Validate end to end

1. Sign in, open `/closet`, tap any item to reach `/closet/:itemId`.
2. Tap the overflow (⋯) trigger — the `BottomSheet` opens with four rows: Edit, Log as worn
   today, Favorite, Delete, in that order, Delete in `danger` tone.
3. **Edit**: tap Edit, change Name and Notes, tap "Save changes". Confirm the read view shows
   the new values; reload the page and confirm they persisted.
4. **Favorite**: tap Favorite. Confirm (via `GET /api/v1/closet/items/{id}` or Supabase Studio)
   the `favorite` column flipped to `true`, and confirm Item detail shows no visible change.
5. **Log as worn today**: tap it once, then again. Confirm (via `item_wears`) exactly one row
   exists for `(item_id, today)` after both taps.
6. **Delete**: tap Delete. Confirm a confirmation dialog appears (design-decisions §22.2) before
   anything is removed. Cancel it once and confirm nothing changed; reopen and confirm it,
   confirm the item is gone from `/closet` and its detail URL now shows the "not found" state.
7. **Offline**: DevTools → Network → Offline. Confirm "Log as worn today" and, inside Edit,
   "Save changes" are visibly disabled; confirm no request fires (Network tab).
8. **Ownership**: as a second user (or via `curl` with a different bearer token), attempt each
   of the four actions against the first user's item id; confirm every one 404s.

## Tests

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check . \
  && uv run mypy . && uv run lint-imports
cd frontend && npm test && npm run lint && npm run typecheck && npm run build
```

See `data-model.md` for the two new/changed tables and `contracts/closet-write.md` for the four
new routes' exact request/response shapes.
