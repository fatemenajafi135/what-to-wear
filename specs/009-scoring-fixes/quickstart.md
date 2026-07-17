# Quickstart: Verifying 009 (Scoring & Retrieval Correctness Fixes)

## Prerequisites

- `cd backend && uv sync --group dev`
- `backend/.env` filled in (gateway keys, Qdrant, `DATABASE_URL`,
  `SUPABASE_URL`) — needed for the eval harness step only; unit tests below
  don't need network/DB access.
- Baseline eval numbers already captured: `docs/eval-baselines/pre-009/` (done
  before implementation started — see that directory's `NOTES.md`).

## 1. Unit-level validation (no network needed)

```bash
cd backend
uv run pytest tests/unit/scoring/test_color_harmony.py -v
uv run pytest tests/unit/scoring/test_combine.py -v
uv run pytest tests/unit/test_colors.py -v
uv run pytest tests/unit/pipeline/test_graph.py -v
```

Expected: all pass, including the new/rewritten color-theory cases (tomato
red + emerald green scores low, navy + charcoal scores high, etc. — see
`spec.md` User Story 1 acceptance scenarios for the exact expected bands),
the new default-strategy assertion in `test_combine.py`, the new
`nearest_names("#0d9488") == ["teal"]` case, and the new
`wardrobe_retrieval` 9th-item-survives-the-cap case.

## 2. Full unit + integration suite

```bash
uv run pytest tests/ -q
```

Expected: no new failures versus `main` (some integration tests hit the live
Supabase DB / are LLM-sampling flaky per `CLAUDE.md`'s documented gotchas —
re-run failed ones in isolation before treating as a regression).

## 3. Lint

```bash
uv run ruff check . && uv run ruff format --check .
```

## 4. Eval no-regression gate (the constitution-required check for any change
   touching scoring/retrieval)

```bash
uv run python -m whattowear.eval.harness
```

Compare `backend/artifacts/eval_runs/*.jsonl` against
`docs/eval-baselines/pre-009/*.jsonl`:

- `retrieval_recall` (deterministic metric) must be byte-identical per case —
  this feature doesn't touch retrieval, only scoring/ranking/narrowing
  downstream of it.
- `owned_only`, `respects_exclusions`, `cites_grounded`,
  `outfit_count_in_range` should hold steady or improve, not regress.
- `weather_appropriate`/generation-dependent numbers may drift run-to-run
  from LLM sampling — don't call a regression from one run (per `CLAUDE.md`).
- Manually spot-check a golden case's `response` field for a color-clash
  outfit (e.g. a wedding case) and confirm the color_harmony score/reason now
  reflects real color theory, not raw contrast — this is the concrete
  "before → after" evidence for the deliverable's Task 5 narrative.

## 5. Manual sanity check (optional, illustrates the bug fix directly)

```python
from whattowear.scoring import color_harmony
from whattowear.schema import Context, WardrobeItem

ctx = Context(occasion="dinner", formality="smart_casual")
navy_charcoal = [
    WardrobeItem(id="a", category="top", colors=["#1b2a4a"], formality="smart_casual", warmth=2),
    WardrobeItem(id="b", category="bottom", colors=["#36454f"], formality="smart_casual", warmth=2),
]
clash = [
    WardrobeItem(id="a", category="top", colors=["#c0392b"], formality="smart_casual", warmth=2),
    WardrobeItem(id="b", category="bottom", colors=["#046307"], formality="smart_casual", warmth=2),
]
print(color_harmony.score(navy_charcoal, ctx))  # expect value >= 0.8
print(color_harmony.score(clash, ctx))          # expect value < 0.45
```
