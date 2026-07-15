# Quickstart: Validating Closet Persistence

## Prerequisites

- Supabase project provisioned, transaction-pooler connection string
  (port 6543) in `.env` as `DATABASE_URL`; optionally the direct connection
  (port 5432) as `DATABASE_URL_DIRECT` for migrations (see research.md →
  pooler gotcha)
- Project ref / JWKS URL in `.env` for ES256 JWT verification (see
  research.md → "JWT verification"; HS256 shared-secret fallback also documented there)
- Existing stack reachable (Qdrant, AI gateway key, LangSmith) — the
  no-regression gate below needs it live
- `uv sync` run in `backend/` to pick up the new dependencies
  (SQLAlchemy, Alembic, `psycopg[binary]`, `pyjwt[crypto]`)

## Setup

```bash
cd backend
uv run alembic upgrade head        # applies 0001_initial_wardrobe_schema
uv run python -m whattowear.crud seed-catalog        # one-time: seeds catalog_items from data/fixtures/wardrobe.json
uv run python -m whattowear.crud seed-eval-baseline  # one-time: seeds the eval baseline user's wardrobe (no-regression gate)
uv run uvicorn whattowear.api:app --reload
```

## Validate the feature end-to-end

Using a valid Supabase JWT for a test user (`$TOKEN`):

1. **Empty closet, populated catalog** — confirms US1 scenario 2 and the
   catalog seed:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" localhost:8000/wardrobe/items      # -> []
   curl -H "Authorization: Bearer $TOKEN" localhost:8000/catalog/items     # -> 40 items
   ```
2. **Add from catalog** (US2) — pick any id from the catalog response above:
   ```bash
   curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"catalog_item_id": "<id>"}' localhost:8000/wardrobe/items
   curl -H "Authorization: Bearer $TOKEN" localhost:8000/wardrobe/items      # -> 1 item, full attributes
   ```
3. **Correct an attribute** (US3):
   ```bash
   curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
     -d '{"formality": "formal"}' localhost:8000/wardrobe/items/<item_id>
   ```
   Then repeat with an invalid value (e.g. `{"formality": "extremely_fancy"}`)
   and confirm a `422`.
4. **Remove an item** (US4):
   ```bash
   curl -X DELETE -H "Authorization: Bearer $TOKEN" localhost:8000/wardrobe/items/<item_id>
   ```
5. **Two-user isolation** (US1 scenario 3): repeat step 2 with a second
   user's token and confirm each user's `GET /wardrobe/items` only shows their
   own item.

## No-regression gate (blocks merge — spec FR-012 / SC-005, constitution Principle I)

```bash
uv run python -m whattowear.eval.harness --strategies baseline hybrid advanced
```

Compare the printed metrics table against `backend/artifacts/eval_runs/`.
Scores must match. If they moved, `context_assembler.load_wardrobe()`'s
Postgres-backed replacement changed retrieval behavior somewhere — stop and
find the divergence before proceeding.
