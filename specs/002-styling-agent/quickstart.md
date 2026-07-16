# Quickstart: Validating the Styling Agent

Validation scenarios per phase. Run from `backend/`. Assumes `.env` is filled
(gateway keys, Qdrant, `DATABASE_URL`, `SUPABASE_URL` — see root `CLAUDE.md`).

## Prerequisites

```bash
uv sync --group dev
uv run alembic upgrade head
uv run python -m whattowear.crud seed-catalog
uv run python -m whattowear.crud seed-eval-baseline   # seeds a user with a closet
```

## Phase 1 — auth gate + unit-test backfill (already implemented on this branch)

```bash
uv run pytest tests/unit/test_colors.py tests/unit/test_categories.py \
  tests/unit/test_cite.py tests/unit/test_query_builder.py \
  tests/unit/test_eval_properties.py tests/unit/test_context_assembler.py -q
```

Expected: all pass, no network/LLM calls needed (colors/categories/cite/
query_builder/eval-properties/context_assembler are pure or fully mocked).

**Note**: `/recommend` (Phase 1's original auth-gate target) and its
`test_recommend_auth.py` coverage were retired at Phase 3 (tasks.md T037a)
once `/suggest` was verified equivalent and the frontend cut over — see
below for the current auth-gate check, now against `/suggest`.

Manual check of the auth gate (now on `/suggest`, `/recommend` no longer exists):

```bash
uv run uvicorn whattowear.api:app --reload &
curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:8000/suggest \
  -H 'Content-Type: application/json' -d '{"occasion": "dinner"}'
# expect: 401 (no bearer token)
```

## Phase 2 — deterministic scoring

```bash
uv run pytest tests/unit/scoring/ -q
```

Expected: each of `color_harmony`, `formality_coherence`, `weather_fitness`,
`silhouette_balance` has unit tests covering at least one clearly-good and one
clearly-bad outfit for that dimension; `combine.py`'s default
(`EQUAL_WEIGHTED_AVERAGE`) and at least one alternative strategy both have tests;
re-scoring the same outfit twice yields identical output (SC-005).

```bash
uv run python -m whattowear.eval.harness
```

Expected: `retrieval_recall` unchanged from the recorded baseline in
`backend/artifacts/eval_runs/` — Phase 2 adds scoring only, no retrieval or
generation change (constitution Principle I gate).

## Phase 3 — graph + `/suggest`

`/recommend` is retired as of this phase (tasks.md T037a) — `/suggest` is the
sole suggestion entrypoint from here on; the frontend was cut over to it
first (T036a-d) so this didn't break the live product.

```bash
uv run uvicorn whattowear.api:app --reload &
TOKEN=$(: obtain a real Supabase JWT for the eval-baseline user, see backend/README.md)
curl -N -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -X POST localhost:8000/suggest \
  -d '{"occasion": "smart dinner", "mood": "put-together"}'
```

Expected: an SSE stream (`event: outfit` chunks followed by `event: done`); the
`done` payload has 3–5 `outfits` (or fewer with a `note`, per closet size), each
with all four `scores` and a `rank_score`; every `items` id resolves in the
eval-baseline user's own closet (no invented or catalog-substituted items).

```bash
uv run python -m whattowear.eval.harness
```

Expected: `retrieval_recall` unchanged from baseline (the graph reuses
`query_builder`/`context_assembler`/retrieval unchanged — Principle I gate); the
LLM-dependent generation checks may drift run-to-run per the known eval-harness
flakiness (see root `CLAUDE.md` gotchas) — don't read a single run as a regression.

## Phase 4 — refinement + optional judge signal

```bash
FIRST=$(curl -sN -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -X POST localhost:8000/suggest -d '{"occasion": "smart dinner"}')
THREAD=$(echo "$FIRST" | grep -o '"thread_id":"[^"]*"' | tail -1 | cut -d'"' -f4)

curl -sN -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -X POST localhost:8000/suggest \
  -d "{\"occasion\": \"warmer\", \"thread_id\": \"$THREAD\"}"
```

Expected: the second response's outfits show a measurably higher average warmth
than the first, while `context.occasion` in the `done` payload is still "smart
dinner" (original request preserved without restating it, FR-013).

```bash
uv run pytest tests/integration/test_suggest_refinement.py -q
```

## No-regression gate (every phase touching retrieval/generation)

```bash
uv run python -m whattowear.eval.harness
# compare retrieval_recall against backend/artifacts/eval_runs/*.jsonl
```

Per root `CLAUDE.md`: `retrieval_recall` is the deterministic metric to compare
across runs; don't declare a regression from a single failed/partial run given the
harness's known flakiness under transient network drops.
