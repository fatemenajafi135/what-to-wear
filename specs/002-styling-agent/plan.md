# Implementation Plan: Styling Agent

**Branch**: `002-styling-agent` (spans all of Feature 002's phases; Phase 1 is
already implemented on it) | **Date**: 2026-07-15 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-styling-agent/spec.md`

## Summary

Turn the existing linear recommendation pipeline into an authenticated,
deterministically-scored, conversationally-refinable styling agent — grounded
entirely in the requester's own closet — without rewriting any of the existing
retrieval, KB, or generation code (constitution Principle I). Delivered as four
independently-mergeable phases (per spec Delivery Phases):

- **Phase 1 — essentials (✅ implemented on this branch).** `/recommend`
  auth-gated behind the existing JWT dependency; `user_id` now comes from the
  verified `sub` claim, never the request body. Unit tests backfilled for
  `colors.py`, `categories.py`, `cite.py`, `pipeline/query_builder.py`,
  `eval/properties.py`, plus a `/recommend` auth integration test. No behavior
  change to retrieval/generation — no eval-gate re-run required.
- **Phase 2 — deterministic scoring.** New `scoring/` package: four pure
  dimension scorers plus a swappable score-combination strategy (FR-009a).
- **Phase 3 — graph + `/suggest`.** The pipeline becomes a LangGraph
  `StateGraph` (node order below) reusing existing stage functions unchanged;
  deterministic pruning/combination/scoring replaces any model-driven item
  picking; `/suggest` (SSE) is delivered, `/recommend` retired within this same
  phase once `/suggest` is verified equivalent **and Feature 003's frontend is
  cut over to it (T036a-d — added by `/speckit.analyze`; the frontend didn't
  exist when this plan was first written)** — `OutfitResult.outfits` becomes
  `list[ScoredOutfit]` in this phase, and `/recommend`'s old code path never
  populates scores, so the two endpoints cannot coexist past Phase 3 without a
  second result type nobody wants to maintain long-term.
- **Phase 4 — refinement.** Conversational refinement via the LangGraph
  checkpointer (already present in `memory/store.py`), swapped from
  `InMemorySaver` to a Postgres-backed saver keyed by `thread_id`; optional
  reported-only LLM judge signal (FR-010).

Technical approach fully resolved in [research.md](./research.md) — no
unresolved unknowns.

## Technical Context

**Language/Version**: Python 3.12, `uv` — unchanged, existing project stack.

**Primary Dependencies**: FastAPI (existing), LangGraph `>=1.0.0,<2.0.0`
(existing dependency, newly used for a graph rather than only the memory
store), LangChain/LangSmith (existing). New: `langgraph-checkpoint-postgres`
(Phase 4 only — swaps the existing `InMemorySaver` for a durable one; see
research.md §5). No other new dependencies (research.md §6: SSE via FastAPI's
built-in `StreamingResponse`, no `sse-starlette`).

**Storage**: Postgres via Supabase (existing, Feature 001) for closet/catalog
data — unchanged. Phase 4 adds LangGraph checkpoint tables (via
`langgraph-checkpoint-postgres`'s own migration, not a hand-rolled schema) to
the same Postgres instance for refinement-thread state.

**Testing**: `pytest` (existing) — new unit tests under `tests/unit/scoring/`
(Phase 2), graph-node tests under `tests/unit/pipeline/` or `tests/integration/`
(Phase 3), a refinement integration test (Phase 4). Existing `eval/harness.py`
no-regression gate re-run after every phase touching retrieval/generation
(Phases 3–4; Phase 2 adds scoring only and Phase 1 changes neither, so neither
requires a gate re-run per constitution Principle I's trigger condition).

**Target Platform**: Linux server (Railway deployment target, unchanged).

**Project Type**: Web service, primarily backend (FastAPI). **Corrected by
`/speckit.analyze` (2026-07-16)**: this line originally said "no frontend
work this feature — `frontend/` stays empty," true when first written and
false now — Feature 003 shipped a real Next.js frontend in the interim, and
its suggest page calls `/recommend` directly. This feature now includes a
small, scoped frontend cutover (tasks T036a-d: an SSE-consumption helper,
regenerated OpenAPI types, pointing the suggest page + result component at
`/suggest`, and a manual smoke test) so retiring `/recommend` (T037a) doesn't
break the live product. Not a full frontend feature — just enough to keep
the existing UI working through the endpoint swap.

**Performance Goals**: No new targets stated in the spec beyond existing
behavior; candidate generation is bounded (research.md §4: k=8 per slot cap)
specifically so `score_and_rank` stays a bounded computation regardless of
closet size, rather than to hit a specific latency number.

**Constraints**: SC-005 (identical scores on repeat = no hidden randomness in
scoring), SC-006 (scoring functions are the literal ones the eval harness
calls, not a reimplementation), FR-014 (prune before combine, cap at k=8/slot,
never brute-force the raw closet).

**Scale/Scope**: Closets up to 200 items (Feature 001 SC-001, unchanged);
3–5 outfits per suggestion (spec FR-002); four dimension scores per outfit
(spec FR-008).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design below.*

| Principle | Check | Status |
|---|---|---|
| I. Existing pipeline is authoritative | Graph nodes wrap `query_builder.py`, `context_assembler.py`, `generator.py`, `cite.py`, retrieval strategies unchanged (research.md §2). No rewrite of any of these. | **PASS** |
| II. Deterministic core, LLM at the edges | Item selection/pruning/combination/ranking is pure Python in `scoring/` and the graph's non-LLM nodes; `generate_outfits` still only assembles from inventory per existing `generator.py` constraints; the LLM never sees or produces the ranking. | **PASS** |
| III. Style knowledge gates wardrobe retrieval | Graph node order is `style_retrieval → build_query → wardrobe_retrieval`, linear, never parallel (research.md §1). | **PASS** |
| IV. Grounded output only | FR-003/FR-011: every outfit item is a closet item; unfillable slots omit the outfit rather than inventing or substituting (spec Future Work) — strictly narrower than the constitution's floor (which permits catalog items), so trivially compliant. | **PASS** |
| V. Scoring functions are eval metrics | `scoring/*.py` functions are the literal functions imported into `eval/harness.py`, not reimplemented there (research.md §3, data-model.md). | **PASS** |
| VI. Schema stability | No new fields on `WardrobeItem`/category groups/formality enum/warmth/seasons/colors; new types (`DimensionScore`, `ScoredOutfit`) are additive wrappers, not taxonomy changes (data-model.md). | **PASS** |
| VII. Single source of truth for contracts | `DimensionScore`, `ScoredOutfit`, `SuggestRequest` are Pydantic models in `schema.py`/`api.py`, the same pattern as existing contracts. **Corrected by `/speckit.analyze`**: frontend now exists (Feature 003) and consumes these via a regenerated `frontend/lib/api-types.ts` (T036b), the same OpenAPI-generation mechanism Feature 003 established — still no hand-maintained duplicate types. | **PASS** |
| Quality Bar — simplicity over abstraction | `scoring/` uses plain functions, not an ABC/class hierarchy (research.md §3) — the one seam (combination strategy) is justified by two concrete strategies existing today, matching the constitution's explicit bar. | **PASS** |

No violations. Complexity Tracking table below is empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-styling-agent/
├── plan.md              # This file
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── suggest.md        # POST /suggest contract
└── tasks.md              # Phase 2 output (/speckit-tasks — not yet created)
```

### Source Code (repository root)

```text
backend/
├── src/whattowear/
│   ├── api.py                       # + POST /suggest (Phase 3); POST /recommend removed at end of Phase 3 (T037a)
│   ├── auth.py                      # unchanged, reused as-is
│   ├── schema.py                    # + DimensionScore, ScoredOutfit, SuggestRequest (additive)
│   ├── colors.py                    # unchanged (Phase 1: unit tests added)
│   ├── categories.py                # unchanged (Phase 1: unit tests added)
│   ├── kb.py                        # unchanged
│   ├── pipeline/
│   │   ├── context_assembler.py     # unchanged, wrapped by graph nodes
│   │   ├── query_builder.py         # unchanged (Phase 1: unit tests added), wrapped by graph nodes
│   │   ├── generator.py             # unchanged, wrapped by graph node
│   │   ├── cite.py                  # unchanged (Phase 1: unit tests added), wrapped by graph node
│   │   ├── run.py                   # existing linear entrypoint; DELETED at end of Phase 3 (T037a) once graph.py + eval/harness.py fully replace it
│   │   └── graph.py                 # NEW (Phase 3): StateGraph, node wiring, GraphState
│   ├── scoring/                     # NEW (Phase 2)
│   │   ├── __init__.py
│   │   ├── color_harmony.py
│   │   ├── formality_coherence.py
│   │   ├── weather_fitness.py
│   │   ├── silhouette_balance.py
│   │   └── combine.py               # FR-009a swappable strategy
│   ├── memory/store.py              # Phase 4: swap InMemorySaver -> PostgresSaver
│   ├── retrieval/                   # unchanged
│   └── eval/
│       ├── harness.py               # + imports scoring/* unchanged (Principle V)
│       └── properties.py            # unchanged (Phase 1: unit tests added)
└── tests/
    ├── unit/
    │   ├── test_colors.py           # Phase 1, done
    │   ├── test_categories.py       # Phase 1, done
    │   ├── test_cite.py             # Phase 1, done
    │   ├── test_query_builder.py    # Phase 1, done
    │   ├── test_eval_properties.py  # Phase 1, done
    │   ├── scoring/                 # NEW (Phase 2): one test file per dimension + combine.py
    │   └── pipeline/test_graph.py   # NEW (Phase 3): node-level unit tests
    └── integration/
        ├── test_recommend_auth.py   # Phase 1, done; DELETED at end of Phase 3 (T037a) — coverage subsumed by test_suggest.py
        ├── test_suggest.py          # NEW (Phase 3)
        └── test_suggest_refinement.py  # NEW (Phase 4)

frontend/                            # Added by /speckit.analyze (2026-07-16) — did not
                                      # exist when this plan was first written; Feature 003
                                      # shipped it in the interim. Phase 3 touches only:
├── lib/
│   ├── api-client.ts                # + SSE-consumption helper (T036a), apiFetch itself untouched
│   └── api-types.ts                 # regenerated from OpenAPI (T036b), not hand-edited
├── app/suggest/page.tsx             # calls /suggest instead of /recommend (T036c)
└── components/SuggestionResult.tsx  # renders the 4 DimensionScores + rank_score (T036c)
```

**Structure Decision**: Single backend project (existing layout, `backend/` only —
constitution "do not restructure the repository layout"). All new code lands
inside `backend/src/whattowear/`, following the existing package boundaries
(`scoring/` is a new top-level package analogous to `retrieval/`/`pipeline/`;
`pipeline/graph.py` joins the existing `pipeline/` package rather than a new
top-level `graph/` package, since it orchestrates the same stage functions
`pipeline/` already owns). The frontend cutover (T036a-d) touches only the
four files listed above — existing files, no new frontend structure.

## Complexity Tracking

*No violations — table intentionally empty.*
