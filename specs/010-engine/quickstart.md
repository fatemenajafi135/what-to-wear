# Quickstart: Validating the Engine Approach

Prerequisites: `backend/.env` filled in (gateway, Qdrant, Supabase,
LangSmith — see repo `CLAUDE.md`), `uv sync --group dev` already run.

## 1. Unit-level: enumeration is correct and bounded

```bash
cd backend
uv run pytest tests/unit/pipeline/test_engine.py -q
```
Expected: counts match a synthetic 3×2×2 closet (skeleton math), full-body
handling and outerwear-crossing cases pass, and the >20,000 safety-valve
case tightens to top-6/slot rather than enumerating unbounded.

## 2. Integration-level: the graph path end-to-end (mocked LLM)

```bash
uv run pytest tests/integration/test_suggest_engine.py -q
```
Expected: `approach: "engine"` returns 3 outfits, every item id resolves to
an owned wardrobe item, every citation resolves to a retrieved rule_id, and
a malformed/out-of-range mocked LLM selection still returns a valid top-3
fallback rather than an error.

## 3. Manual smoke test against the live stack

```bash
uv run uvicorn whattowear.api:app --reload
```

In another shell, using a seeded test user's bearer token (see
`eval/test_users.py` / existing manual-testing convention in
`specs/002-styling-agent/quickstart.md`):

```bash
curl -s -X POST http://localhost:8000/suggest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"occasion": "wedding", "temp_c": 5, "approach": "engine"}'
```
Expected: an SSE stream with 3 `outfit` events + one `done` event, same
shape as an `approach`-omitted request against the same user/context.

Confirm the default is unchanged by re-running the same request with
`approach` omitted entirely and diffing the two responses' `outfits[].items`
sets — they are expected to *differ* (different selection mechanism) but
both must independently satisfy grounding (every item owned).

## 4. Regenerate frontend types (constitution Principle VII)

With the backend still running from step 3:

```bash
cd frontend
npm run fetch:openapi
git diff lib/api-types.ts   # confirm only the new `approach` field appears
```

## 5. Full affected-suite regression check

```bash
cd backend
uv run pytest tests/ -q
uv run ruff check . && uv run ruff format --check .
```
Expected: 351 pre-existing tests still pass (this feature's baseline,
captured before branching) plus the new engine tests, ruff clean. The full
eval no-regression harness (`uv run python -m whattowear.eval.harness`) is
**not required** for this merge — `approach` is opt-in only, so the default
path's eval numbers are provably unaffected (per
`docs/ai-v2-session-handoff.md`'s scoping decision, recorded in plan.md's
Summary).
