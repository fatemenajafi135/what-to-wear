# Quickstart: Validating L1/L3 Retrieval Restructure + Refinement Warmth-Floor Fix

All commands run from `backend/`. Needs the same environment every eval/integration run in this repo
needs: `backend/.env` filled in (gateway keys, `TAVILY_API_KEY`, Qdrant URL/key, `DATABASE_URL`,
`SUPABASE_URL`) and network access.

## Prerequisites

```bash
uv sync --group dev
uv run alembic upgrade head   # if not already current
```

## 1. Confirm the L1 semantic pool exists and is queryable (Task A)

```bash
uv run python -m whattowear.ingest.build_kb --sample-check
```

Expected: per-layer chunk counts include `L1` chunks with `granularity: section` alongside the atomic
cards (visible in the `-v` verbose log if run with `-v` too); the report's final line still reads `OK:
metadata complete, rule_ids unique, no reference-only book text stored.` — the guard from
`build_kb._print_report` that Task A must not break.

```python
# uv run python
from whattowear.retrieval.hybrid import retrieve_l1
from whattowear.kb import get_kb
from whattowear.schema import Context

kb = get_kb()
ctx = Context(occasion="wedding", formality="formal")
chunks = retrieve_l1(kb, ctx)
assert any(c.metadata.get("granularity") == "section" for c in chunks), "semantic branch returned nothing"
assert any(c.metadata.get("granularity") == "atomic" for c in chunks), "atomic load-all regressed"
print(len(chunks), {c.metadata["granularity"] for c in chunks})
```

Expected outcome: both `"atomic"` and `"section"` chunks present — SC-001.

## 2. Confirm a live Tavily call happens and degrades gracefully (Task B)

```python
# uv run python
from whattowear.retrieval.hybrid import retrieve_l3
from whattowear.pipeline import query_builder
from whattowear.schema import Context

ctx = Context(occasion="office", formality="business_casual", season="autumn")
docs = retrieve_l3(query_builder.l3_query(ctx))
assert docs, "expected live Tavily results for a seasoned query"
assert all(d.metadata["layer"] == "L3" and d.metadata["rule_id"].startswith("L3-live-") for d in docs)
print([d.metadata["url"] for d in docs])
```

Expected outcome: a handful of `Document`s with real URLs, fetched just now (SC-003). To confirm
graceful degradation, temporarily unset `TAVILY_API_KEY` (or point `WTW_QDRANT_URL`/network off) and
re-run — expect `retrieve_l3` to return `[]` and log a warning, not raise (SC-004).

Then confirm the graph-level ordering and grounding end to end:

```bash
uv run pytest tests/integration/test_suggest_refinement.py -q -k Warmer
```

and check a LangSmith trace for a real `/suggest` call (`uv run uvicorn whattowear.api:app --reload`,
then `POST /suggest` with a `season`-bearing occasion) shows the live Tavily call as its own visible
step under `node.style_retrieval`.

## 3. Confirm the warmth-floor fix (Task C)

**Before capturing the fix, run once on the pre-fix code** (this is the one and only chance to get a
real "before" number — see `research.md` D9):

```bash
uv run python scripts/warmth_floor_evidence.py --out artifacts/warmth_floor_before.json
```

Apply the code change (`pipeline/graph.py`), then:

```bash
uv run python scripts/warmth_floor_evidence.py --out artifacts/warmth_floor_after.json
uv run pytest tests/unit/pipeline/test_graph.py -q -k WarmerDelta
```

Expected outcome: the after run's fallback rate is lower than the before run's (SC-005); the unit
tests assert the new relative-floor behavior (a low-ceiling category gets a small nonzero floor, not a
full exemption, and never a floor above its own ceiling).

## 4. Full no-regression gate

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest tests/ -q
uv run python -m whattowear.eval.harness
```

Expected: full suite green. `retrieval_recall` for `baseline` is byte-identical to the archived
`artifacts/eval_runs/baseline.jsonl` (SC-006 — this feature is designed to leave baseline's corpus
untouched). `hybrid`/`advanced` recall may move on exactly the 3 golden cases whose static L3 pin was
removed (`research.md` D7) — any other movement is a real regression to investigate, not an expected
side effect.
