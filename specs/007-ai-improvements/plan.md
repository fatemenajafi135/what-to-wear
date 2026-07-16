# Implementation Plan: L1/L3 Retrieval Restructure + Refinement Warmth-Floor Fix

**Branch**: `007-AI-improvements` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-ai-improvements/spec.md`

## Summary

Three independent, additive changes to the existing retrieval/refinement pipeline, none of which touch
`scoring/`, the graph's node order, or the frozen schema:

1. `retrieve_l1()` gains a `similarity_search` branch over long-form section-chunks that `build_kb.py`
   already embeds into the L1 layer (Wikipedia color-theory/harmony/complementary-colors, Chevreul,
   Munsell) but that retrieval never queries today — unioned with the existing atomic load-all.
2. `retrieve_l3()` stops querying the static pre-ingested trend collection and instead calls the
   existing `external/trends.search_trends()` Tavily wrapper live, at request time, turning results into
   citable `Document`s with a synthetic `rule_id`. Degrades to `[]` on failure/timeout.
3. `pipeline/graph.py`'s "warmer" refinement floor replaces its blanket footwear/accessory exemption
   with a floor scaled to each category's own achievable warmth ceiling (computed from `ctx.wardrobe`),
   capped so a category is never fully excluded by its own floor.

## Technical Context

**Language/Version**: Python 3.12, `uv`

**Primary Dependencies**: FastAPI, LangGraph, LangChain (`langchain-qdrant`, `langchain-tavily`),
Qdrant, LangSmith tracing (all already in use — no new dependencies added)

**Storage**: Qdrant (existing `whattowear_kb` collection, no schema change — new similarity_search
branch queries chunks already embedded there); no Postgres schema change

**Testing**: `pytest` (`backend/tests/unit`, `backend/tests/integration`), `ruff`, the existing eval
harness (`backend/src/whattowear/eval/harness.py`)

**Target Platform**: Existing backend service (Railway), unchanged

**Project Type**: Web service backend — single `backend/` package, no frontend or contract changes
(`/suggest`'s request/response shape is unchanged; this feature only changes what happens inside
`style_retrieval` and `wardrobe_retrieval`)

**Performance Goals**: No new SLA; L3 moving from a cached static vector search to a live Tavily call
trades some added per-request latency for freshness — no numeric target set (research.md documents why:
the existing weather-lookup fallback pattern is the precedent, and Feature 005's cache still wraps the
whole `/suggest` call, absorbing this on cache hits)

**Constraints**: Constitution Principles I (existing pipeline authoritative — additive, not a rewrite),
II (LLM never selects/scores), III (style retrieval strictly gates wardrobe retrieval), IV (grounded
output only — new L1 chunks and live Tavily results must both be citable/verifiable), V (scoring
functions untouched), VI (schema frozen)

**Scale/Scope**: Same golden set (25 cases), same three retrieval strategies (baseline/hybrid/advanced),
same single-user-request shape — no scale change

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — see below.*

| Principle | Check | Status |
|---|---|---|
| I. Existing pipeline authoritative | L1/L3 changes are additive to `retrieval/hybrid.py` and `retrieval/advanced.py`; `retrieval/baseline.py` and `scoring/` are not touched. The warmth-floor fix is a targeted change inside one existing function (`_item_fits_hard_constraints`), not a rewrite of `wardrobe_retrieval`'s overall pruning strategy. | PASS |
| II. Deterministic core, LLM at the edges | Neither change adds an LLM call to selection/scoring. `similarity_search` and Tavily search are retrieval (fetching candidate text), not generation or ranking — item selection stays in `generate_outfits`/`score_and_rank`, unchanged. The warmth-floor fix is pure arithmetic over `ctx.wardrobe`. | PASS |
| III. Style knowledge gates wardrobe retrieval | `style_retrieval` (which calls `_retrieve` → `hybrid.retrieve`/`advanced.retrieve` → `retrieve_l1`/`retrieve_l3`) already runs before `wardrobe_retrieval` in `build_graph()`'s edge list. Neither Task A nor Task B changes graph node order or introduces a parallel branch — the live Tavily call happens inside the same `style_retrieval` node, so the ordering guarantee is structural, not just observed. | PASS |
| IV. Grounded output only | New L1 semantic chunks carry the same `{source, url, layer, rule_id}` metadata the existing atomic cards do (stamped by `chunk_section`, already validated by `build_kb._validate`) — `cite.py` needs no changes to cite them. Live Tavily results are synthesized into `Document`s carrying the same four keys, so `cite.all_cites_grounded` (`retrieved_ids` = `retrieval.rule_ids()`) verifies them identically. No item selection is affected — grounding of *wardrobe items* (Feature 005's `verify_grounding` node) is untouched by either change. | PASS |
| V. Scoring functions are eval metrics | No file under `scoring/` is touched. The AST-walking test (`tests/unit/test_judge.py`) asserting no LLM import in `scoring/*.py` continues to pass unchanged. | PASS |
| VI. Schema stability | No change to `schema.py`, `categories.py`, formality enum, warmth range, or category groups. The warmth-floor fix reads `item.warmth` (already 0-5) and `categories.group_of()` (already frozen); it does not add a new field or a parallel scale. | PASS |

No violations — Complexity Tracking table is not needed.

## Project Structure

### Documentation (this feature)

```text
specs/007-ai-improvements/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks, not this command)
```

No `contracts/` directory — this feature changes no external interface. `POST /suggest`'s request and
response schemas (`schema.py`'s `SuggestResult`, `CitedSource`, etc.) are unchanged; the changes are
entirely inside what `style_retrieval` and `wardrobe_retrieval` do internally.

### Source Code (repository root)

```text
backend/
├── src/whattowear/
│   ├── retrieval/
│   │   ├── hybrid.py         # MODIFY: retrieve_l1() gains a semantic-chunk branch;
│   │   │                     #   retrieve_l3() switches from static vector search to
│   │   │                     #   live Tavily
│   │   ├── advanced.py       # MODIFY: retrieve_l3 call site over-fetches live results
│   │   │                     #   before the existing Cohere rerank (shape unchanged)
│   │   └── baseline.py       # UNCHANGED
│   ├── external/
│   │   └── trends.py         # UNCHANGED — search_trends() already exists, reused as-is
│   ├── pipeline/
│   │   ├── query_builder.py  # UNCHANGED — route()/l3_query() reused as-is
│   │   └── graph.py          # MODIFY: _item_fits_hard_constraints()'s warmer-floor
│   │                         #   branch; _WARMTH_FLOOR_EXEMPT_GROUPS removed
│   ├── ingest/
│   │   └── build_kb.py       # UNCHANGED — chunking/embedding already produces what
│   │                         #   Task A queries; re-run (not modify) to confirm the
│   │                         #   reference-only guard still passes
│   └── kb.py                 # UNCHANGED
├── data/
│   ├── kb/manifest.yaml      # UNCHANGED — l3_trend_cards.jsonl stays ingested (baseline
│   │                         #   still needs it in the whole-collection corpus)
│   └── golden_set.yaml       # MODIFY: 3 cases' relevant_rule_ids drop the now-
│                             #   unreproducible static L3 pin, per FR-007/research.md
├── tests/
│   ├── unit/retrieval/test_hybrid.py          # NEW: retrieve_l1 semantic branch,
│   │                                           #   retrieve_l3 live-Tavily mapping + fallback
│   ├── unit/retrieval/test_advanced.py        # NEW: L3 over-fetch + rerank shape preserved
│   ├── unit/pipeline/test_graph.py            # MODIFY: warmer-floor tests
│   └── integration/test_suggest_refinement.py # MODIFY: drop _WARMTH_FLOOR_EXEMPT_GROUPS
│                                               #   reference, assert new behavior
└── artifacts/
    └── eval_runs/             # eval harness output — before/after warmth-floor evidence
                                #   captured separately (see quickstart.md), not committed
                                #   here (gitignored, matches existing convention)
```

**Structure Decision**: No new files, no new packages. Every change lands inside a file that already
exists and already owns this responsibility (`retrieval/hybrid.py` for both L1 and L3 retrieval logic,
`pipeline/graph.py` for refinement pruning) — consistent with Principle I and the constitution's
simplicity clause: this is a solo project, no new abstraction layer is justified for three targeted
behavior changes.

## Complexity Tracking

*No violations — table not needed.*
