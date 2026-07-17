# Implementation Plan: Scoring & Retrieval Correctness Fixes

**Branch**: `009-scoring-fixes` (git branch `feature/009-scoring-fixes`, per the
owner's `feature/NNN-name` convention starting at 009 — the spec directory
name and git branch name are intentionally independent) | **Date**: 2026-07-17
| **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/009-scoring-fixes/spec.md`

## Summary

Four targeted, independent fixes to already-shipped deterministic scoring and
retrieval-narrowing code, found by direct code review ahead of a
certification-challenge resubmission: (1) rewrite the inverted color-harmony
scorer to use real color-theory (neutral/analogous favored, unbalanced
complementary and 4+-hue clashes penalized) instead of raw WCAG contrast; (2)
switch the default outfit-ranking combination strategy from equal-weighted
average to the existing, already-tested `fit_first_lexicographic`; (3) sort
each clothing slot's candidates by formality/warmth fitness *before* applying
the existing per-slot retention cap in `wardrobe_retrieval`, so the cap can no
longer silently drop the best-fitting item; (4) add several missing common
color names to the plain-language color lookup table. All four are additive,
same-shape changes to existing modules — no schema, API, or dependency change
(constitution Principle I: extend, don't rewrite).

## Technical Context

**Language/Version**: Python 3.12 (existing backend, unchanged)

**Primary Dependencies**: None new. Reuses existing `pydantic`, the project's
own `colors.py`, `categories.py`, `schema.py` (`FORMALITY_ORDER`), and
`pipeline/context_assembler.infer_formality`.

**Storage**: N/A — pure in-memory scoring/sorting logic, no persistence change.

**Testing**: pytest (`backend/tests/unit/`), existing eval harness
(`uv run python -m whattowear.eval.harness`) as the no-regression gate.

**Target Platform**: Linux server (existing FastAPI backend, unchanged).

**Project Type**: Web service (backend-only change; no frontend/API surface
touched).

**Performance Goals**: No explicit target — the changed code paths (per-slot
sort of ≤8-ish candidates, a 4-value HSL comparison) are trivially fast
relative to the LLM calls already in the pipeline; no perf regression risk.

**Constraints**: Must not change `SuggestResult`/`SuggestRequest` shapes, the
`DimensionScore` shape, the category-group/formality taxonomy, or the
semantics of `_is_slot_complete`/`_is_valid_combination` (constitution
Principle VI, spec FR-011/FR-012).

**Scale/Scope**: Same as today's production wardrobe/candidate sizes (per-slot
candidates already capped at `_CANDIDATES_PER_SLOT = 8`); no scale change.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Existing Pipeline Is Authoritative** — PASS. All four changes edit
  existing functions in place (`color_harmony.score`, `combine.rank_outfits`'s
  default parameter, `wardrobe_retrieval`'s sort step, `FASHION_COLOR_PALETTE`)
  rather than rewriting retrieval/ingest/KB/eval wholesale. The eval
  no-regression gate (`docs/eval-baselines/pre-009/`) is the required
  before/after evidence.
- **II. Deterministic Core, LLM At The Edges** — PASS. All four fixes are pure
  Python; no LLM call is added or touched. (This feature does not attempt WP2
  "Engine" — that's a separate, later branch per the owner's sequencing.)
- **III. Style Knowledge Gates Wardrobe Retrieval** — PASS/N/A. This feature
  doesn't touch the KB-query-first ordering; `wardrobe_retrieval`'s change is
  purely about which items survive the existing per-slot cap, not when it
  runs relative to style retrieval.
- **IV. Grounded Output Only** — PASS/N/A. No change to item grounding or
  citation logic.
- **V. Scoring Functions Are Eval Metrics** — PASS. The rewritten
  `color_harmony.score()` stays a pure function reused unchanged by both the
  graph and the eval harness (no fork); its rule_ids (`L1-color-*`) are
  human-readable strings in the `reason` field, not a metric that only an LLM
  can compute.
- **VI. Schema Stability** — PASS. No new/renamed category groups, no parallel
  formality scale (FR-008's warmth-distance mapping and the sort key both
  reuse the existing `FORMALITY_ORDER`/warmth 0-5 scale directly, per
  spec Assumptions).
- **VII. Single Source Of Truth For Contracts** — PASS/N/A. No API contract
  changes; nothing for the frontend to regenerate.

No violations. Complexity Tracking table not needed.

## Project Structure

### Documentation (this feature)

```text
specs/009-scoring-fixes/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── scoring-interfaces.md   # internal function-signature contract (no external API changes)
└── tasks.md              # Phase 2 output (/speckit-tasks, not this command)
```

### Source Code (repository root)

```text
backend/
├── src/whattowear/
│   ├── colors.py                       # + hex_to_hsl(), + 8 FASHION_COLOR_PALETTE entries
│   ├── scoring/
│   │   ├── color_harmony.py            # score() rewritten (T0.1)
│   │   └── combine.py                  # rank_outfits() default strategy changed (T0.2)
│   └── pipeline/
│       └── graph.py                    # wardrobe_retrieval() sorts before the per-slot cap (T0.3)
└── tests/unit/
    ├── scoring/
    │   ├── test_color_harmony.py       # rewritten (delete inverted-bug test, add color-theory tests)
    │   └── test_combine.py             # default-strategy assertion updated
    ├── test_colors.py                  # + nearest_names("#0d9488") == "teal"
    └── pipeline/test_graph.py          # + one wardrobe_retrieval sort-before-cap test
```

**Structure Decision**: Existing `backend/` single-service layout, unchanged.
No new files except the spec-kit documentation artifacts and one new function
(`hex_to_hsl`) inside the already-existing `colors.py` — this feature adds
zero new source modules.

## Complexity Tracking

*No Constitution Check violations — table not needed.*
