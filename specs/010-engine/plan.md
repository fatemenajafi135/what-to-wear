# Implementation Plan: Engine Approach (Deterministic Selection)

**Branch**: `010-engine` (git branch: `feature/010-engine`) | **Date**: 2026-07-17 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-engine/spec.md`

## Summary

Add a new, opt-in `approach:"engine"` value to `POST /suggest` that routes a
request through a Principle-II-compliant selection path: deterministically
enumerate every valid outfit combination from the already-pruned candidates,
score all of them with the existing unchanged scorer, and let the LLM only
pick-and-narrate an ordered 3 from the top-6 shortlist (never invent a
combination, never re-rank outside a validated fallback). Folds the
`SuggestRequest.approach`/`GraphState.approach` plumbing (WP0 T0.5) into this
same branch since engine is its only consumer. Default behavior (`approach`
omitted or `"grounded"`) is byte-for-byte unchanged — this is a pure addition
alongside the existing linear graph, not a rewrite of it, so the full eval
no-regression gate is not required for this merge (per
`docs/ai-v2-session-handoff.md`'s scoping decision).

## Technical Context

**Language/Version**: Python 3.12 (backend, unchanged), TypeScript/Next.js
(frontend — only a generated-types regen, no new UI in this feature).

**Primary Dependencies**: FastAPI, LangGraph (`StateGraph` conditional edges,
new to this codebase — existing graph is currently pure linear edges),
Pydantic (structured LLM output), `langchain-litellm` `ChatLiteLLM` (existing
`config.get_chat_model`, reused unchanged).

**Storage**: None new. Reuses existing Postgres-backed wardrobe/catalog reads
(`crud.py`) and the existing Postgres-backed LangGraph checkpointer
(`memory/store.py`). No migration.

**Testing**: pytest — unit tests under `tests/unit/pipeline/`, integration
tests under `tests/integration/`, matching existing file/class conventions
(see `tests/unit/pipeline/test_graph.py`, `tests/integration/test_suggest.py`).

**Target Platform**: Linux server (Railway), unchanged.

**Project Type**: Web service (FastAPI backend + Next.js frontend) — existing
`backend/`/`frontend/` layout, not restructured.

**Performance Goals**: Interactive chat-turn latency (same practical budget
as the existing `generate_outfits` path — no new hard SLA). Bounded
explicitly by the >20,000-combo safety valve (FR-010) rather than an
unbounded enumeration.

**Constraints**: Opt-in only (FR-012) — zero behavior change for any request
that omits the field. Reuse existing coherence guards (`_is_valid_combination`,
`_is_slot_complete`) and the existing scorer (`score_outfits`) unchanged
(constitution Principle I, V) — this feature must not fork either. Exactly
one LLM call in the new path's selection step (`engine_write`).

**Scale/Scope**: Candidates are already capped at 8/slot by the existing
`wardrobe_retrieval` node before this feature ever sees them. Worst case
(8 top × 8 bottom × 8 footwear × 8 outerwear = 4096, plus 8 full_body × 8
footwear × 8 outerwear = 512) stays under the 20,000-combo valve threshold
with today's `_CANDIDATES_PER_SLOT=8` — the valve exists for defense-in-depth
if that cap ever changes, not because today's numbers require it.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Existing Pipeline Is Authoritative** — PASS. `pipeline/engine.py` is
  new; it imports `_is_valid_combination`/`_is_slot_complete` from
  `pipeline/graph.py` rather than reimplementing them, and calls
  `scoring.score_outfits` unchanged. No existing module is rewritten.
- **II. Deterministic Core, LLM At The Edges** — PASS for the new path itself
  (this feature's entire purpose): item selection is enumerate+score, pure
  Python; the LLM only picks an index and writes text, and any invalid pick
  is deterministically discarded (FR-006). **Known, pre-existing, explicitly
  out-of-scope condition**: the *default* (`grounded`) path's
  `generate_outfits` still has the LLM assemble combinations directly, which
  does not itself comply with Principle II. This feature does not touch or
  "fix" that path — per `docs/claude-code-implementation-spec.md`'s own
  instruction, `direct`/`grounded` stay as evaluated comparison baselines,
  and the constitution amendment recording their explicit exemption is
  tracked as separate follow-up work, not a blocker for landing this
  additive feature (the amendment doesn't change any code, only the
  constitution text).
- **III. Style Knowledge Gates Wardrobe Retrieval** — PASS. The engine path
  reuses the exact same node order up through `wardrobe_retrieval`
  (`gather_context → style_retrieval → wardrobe_retrieval`); it only branches
  after that point.
- **IV. Grounded Output Only** — PASS. `verify_grounding` still runs
  unchanged, after `engine_write`, before `explain` — same safety net, same
  semantics, on both paths.
- **V. Scoring Functions Are Eval Metrics** — PASS. `score_outfits` /
  `DIMENSION_SCORERS` are called unchanged; this feature adds no new scoring
  dimension and no second scoring implementation.
- **VI. Schema Stability** — PASS. No category-group, formality-enum,
  warmth-range, or color representation changes. `SuggestRequest` gains one
  new optional field (`approach`); `GraphState` gains one new key. Neither
  touches the frozen item taxonomy.
- **VII. Single Source Of Truth For Contracts** — Applies: adding
  `SuggestRequest.approach` changes the OpenAPI schema, so
  `frontend/lib/api-types.ts` must be regenerated from a running backend
  instance (`npm run fetch:openapi`), not hand-edited. Included as an
  explicit task.

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/010-engine/
├── plan.md              # This file
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── suggest-engine.md # Phase 1 output — request/response contract delta
└── tasks.md              # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── src/whattowear/
│   ├── schema.py                    # + SuggestRequest.approach, + EngineSelection/EngineWriteOutput
│   ├── api.py                       # pass approach through; cache-key/seed extension
│   └── pipeline/
│       ├── graph.py                 # + GraphState.approach, + conditional edge,
│       │                            #   + engine_enumerate_and_score, + engine_write nodes
│       ├── engine.py                # NEW — enumerate_outfits(), engine_write() LLM call + validation/fallback
│       └── cache.py                 # + approach in compute_cache_key() material
└── tests/
    ├── unit/pipeline/
    │   └── test_engine.py           # NEW — enumeration unit tests
    └── integration/
        └── test_suggest_engine.py   # NEW — engine-approach integration test

frontend/
└── lib/api-types.ts                 # regenerated (npm run fetch:openapi against a local backend)
```

**Structure Decision**: Existing `backend/`/`frontend/` layout, unchanged.
One new backend module (`pipeline/engine.py`), targeted edits to three
existing backend files, two new backend test files, one regenerated
frontend types file. No new top-level directories, no repository/service
layer introduced (Quality Bar: simplicity — `engine.py` is plain functions
and Pydantic models, matching `generator.py`'s existing style).

## Complexity Tracking

*No Constitution Check violations — table not needed.*
