# Tasks: Scoring & Retrieval Correctness Fixes

**Input**: Design documents from `/specs/009-scoring-fixes/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/scoring-interfaces.md, quickstart.md

**Tests**: Included — the constitution's Quality Bar requires unit tests for
deterministic logic, and the source bug report specified exact test cases.

**Organization**: Tasks are grouped by user story (US1-US4, spec.md priorities)
so each of the four independent fixes can be implemented and verified on its
own. All four touch disjoint logic (no story depends on another's changes),
though US1 and US4 both edit `colors.py` in different, non-overlapping regions.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US4)
- Paths are relative to `backend/` unless stated otherwise

## Phase 1: Setup

- [x] T001 Create git branch `feature/009-scoring-fixes` off `main`
- [x] T002 Snapshot the pre-implementation eval baseline: copy
      `backend/artifacts/eval_runs/*.jsonl` to `docs/eval-baselines/pre-009/`
      (gitignored source, this is the only durable "before" record) —
      done, see `docs/eval-baselines/pre-009/NOTES.md`

---

## Phase 2: Foundational

**None required.** All four user stories touch disjoint code paths with no
shared blocking prerequisite beyond what Phase 1 already covers.

---

## Phase 3: User Story 1 - Color harmony reflects real styling principles (Priority: P1) 🎯 MVP

**Goal**: Replace the inverted WCAG-contrast color-harmony scorer with a
color-theory-based one (neutral/analogous favored, unbalanced-complementary
and 3+-clash penalized), per `research.md` Decision 1's exact rule table.

**Independent Test**: Score the fixed set of outfit candidates from
`spec.md` US1's acceptance scenarios in isolation (no other scoring
dimension, no ranking, no retrieval involved) and confirm the ordering
matches color-theory expectations.

### Tests for User Story 1 ⚠️

> Write these first; they must fail (ImportError/AttributeError on the new
> function, or wrong-value assertions against the current inverted scorer)
> before implementation.

- [x] T003 [P] [US1] Add `hex_to_hsl` unit tests to
      `backend/tests/unit/test_colors.py` — known hex values with expected
      (h, s, l) (e.g. pure red `#ff0000` → h≈0°, pure neutral gray → s≈0,
      a known dark navy → l in the low band)
- [x] T004 [P] [US1] Rewrite `backend/tests/unit/scoring/test_color_harmony.py`:
      delete `test_high_contrast_pair_scores_higher_than_low_contrast_pair`
      (encodes the inverted bug), add cases for each `spec.md` US1 acceptance
      scenario — tomato red (`#c0392b`-family) + emerald green <0.45; navy +
      charcoal (+white shirt) ≥0.8; oatmeal + camel + cream ≥0.8; navy +
      mustard as accent ≥0.7 vs. equal-weight navy+mustard <0.5; burgundy +
      blush pink (analogous) ≥0.7; 4 saturated distinct hues <0.3; keep the
      existing determinism/bounds/reason-present tests

### Implementation for User Story 1

- [x] T005 [US1] Add `hex_to_hsl(hex_color: str) -> tuple[float, float, float]`
      to `backend/src/whattowear/colors.py`, next to `_hex_to_rgb`, matching
      the file's existing style (depends on T003 existing to validate against)
- [x] T006 [US1] Rewrite `score()` in
      `backend/src/whattowear/scoring/color_harmony.py` per `research.md`
      Decision 1's full rule table (neutral partition incl. named-neutral
      palette override, chromatic-count base score, value-contrast +0.1
      bonus, clamp to [0,1], `reason` naming the fired `L1-color-*` rule id)
      — keep the `score(items, ctx) -> DimensionScore` signature unchanged.
      **Deviated from the original description**: the value-contrast bonus
      turned out to use HSL lightness, not `contrast_ratio` — `contrast_ratio`
      stays untouched/public but is no longer called here (found during
      implementation, see research.md Decision 2 addendum). The midband
      score (40-150°) was also revised 0.4→0.3 after the spec's own required
      test case failed arithmetic at 0.4 (research.md Decision 1 addendum)
      (depends on T005)
- [x] T007 [US1] Run `cd backend && uv run pytest tests/unit/scoring/test_color_harmony.py tests/unit/test_colors.py -v` and confirm all green (depends on T005, T006) — 46 passed

**Checkpoint**: Color-harmony scoring is correct and independently verified —
this alone is the deliverable's headline "found by eval/review → fixed →
re-measured" story (Task 5 narrative).

---

## Phase 4: User Story 2 - Outfit ranking prioritizes wearability over cosmetic tiebreaks (Priority: P1)

**Goal**: Make weather/formality fit the primary ranking signal by default,
using the existing, already-tested `fit_first_lexicographic` strategy
instead of a flat equal-weighted average.

**Independent Test**: Two candidate outfits with identical average score but
different weather/formality fit — confirm default ranking puts the
better-fitting one first, with no other dimension or story involved.

### Tests for User Story 2 ⚠️

- [x] T008 [P] [US2] Update
      `backend/tests/unit/scoring/test_combine.py::TestRankOutfits::test_default_strategy_is_equal_weighted_average`
      — replace with a test asserting the default strategy is
      `fit_first_lexicographic` (rename the test to reflect the corrected
      behavior per this project's "replace, don't weaken" rule for tests
      that encode now-wrong behavior). Also add a second assertion in the
      same test (or a sibling test) that calls `combine.rank_outfits([...])`
      with **two** outfits tied on `equal_weighted_average` but differing on
      weather/formality fit (reuse the exact two-outfit construction from
      `TestFitFirstLexicographic`'s existing test) and no explicit `strategy`
      arg, confirming the better-fitting one ranks first end-to-end through
      the default parameter — not just that the two functions independently
      behave correctly (`/speckit.analyze` finding F3: the default-identity
      check alone doesn't prove the tie-break wiring)

### Implementation for User Story 2

- [x] T009 [US2] In `backend/src/whattowear/scoring/combine.py`, change
      `rank_outfits`'s default `strategy` parameter from
      `EQUAL_WEIGHTED_AVERAGE` to `fit_first_lexicographic` (depends on T008)
- [x] T010 [US2] Run `cd backend && uv run pytest tests/unit/scoring/test_combine.py -v` and confirm green (depends on T009) — 6 passed

**Checkpoint**: Default ranking now prioritizes wearability; independently
verified via `test_combine.py` alone.

---

## Phase 5: User Story 3 - The best-fitting items in a slot are never silently dropped (Priority: P1)

**Goal**: Sort each clothing slot's candidates by formality/warmth fitness
before `wardrobe_retrieval` applies the existing `_CANDIDATES_PER_SLOT` cap,
so best fit — not closet order — determines what survives.

**Independent Test**: A slot with more candidates than the cap where only
one item (placed after the cap boundary in closet order) is the exact
formality match — confirm it survives narrowing, independent of scoring or
ranking downstream.

### Tests for User Story 3 ⚠️

- [x] T011 [P] [US3] Add a `wardrobe_retrieval` unit test to
      `backend/tests/unit/pipeline/test_graph.py`: build a 10-item slot where
      only the 9th item (by input order) is the exact formality match to
      `ctx.formality`; assert it's present in `candidates` after the node
      runs (i.e. survives the per-slot cap)

### Implementation for User Story 3

- [x] T012 [US3] In `wardrobe_retrieval` (`backend/src/whattowear/pipeline/graph.py`),
      sort each slot's item list — key = `(abs(FORMALITY_ORDER[item.formality] -
      FORMALITY_ORDER[ctx.formality]), warmth_distance)` ascending, per
      `research.md` Decision 4 — immediately before the existing
      `items[:_CANDIDATES_PER_SLOT]` slice. No inference fallback needed:
      `ctx.formality` is already guaranteed populated by
      `context_assembler.assemble_context()` on every path that builds
      `ctx` (confirmed by `/speckit.analyze`, finding F1 — an earlier draft
      assumed a fallback was needed here; it isn't). `warmth_distance` via a
      new `_IDEAL_WARMTH_BY_BAND` mapping (freezing→4, cold→3, cool→2,
      mild→2, warm→1, hot→0; 0 if no `temp_band`), placed near the existing
      `_MAX_WARMTH_BY_BAND` — a distinct constant, not a replacement (the
      existing one is a hard-constraint ceiling, this is a ranking target).
      Reuse the already-imported `FORMALITY_ORDER`; don't invent a parallel
      formality scale (depends on T011)
- [x] T013 [US3] Run `cd backend && uv run pytest tests/unit/pipeline/test_graph.py -v` and confirm green (depends on T012) — 37 passed

**Checkpoint**: The best-fitting items per slot can no longer be silently
dropped before generation; independently verified.

---

## Phase 6: User Story 4 - Color names shown to the user are accurate (Priority: P2)

**Goal**: Add the missing common color names to `FASHION_COLOR_PALETTE` so
nearest-name lookup stops misidentifying them via distant fallbacks.

**Independent Test**: Look up a previously-unmatched hex (e.g. `#0d9488`,
teal-ish) and confirm the correct name is returned — independent of any
scoring or retrieval logic.

### Tests for User Story 4 ⚠️

- [x] T014 [P] [US4] Add a test to `backend/tests/unit/test_colors.py`
      asserting `nearest_names(["#0d9488"]) == ["teal"]` (not "sage" or
      "light blue")

### Implementation for User Story 4

- [x] T015 [US4] Add to `FASHION_COLOR_PALETTE` in
      `backend/src/whattowear/colors.py`, in the comment-grouped section
      matching each color's family: `red #c0392b`, `orange #e67e22`,
      `coral #ff7f50`, `pink #f8a1c4`, `teal #008080`, `turquoise #40e0d0`,
      `forest green #228b22`, `mint #98d8aa` (depends on T014)
- [x] T016 [US4] Run `cd backend && uv run pytest tests/unit/test_colors.py -v` and confirm green (depends on T015) — 35 passed

**Checkpoint**: All four user stories independently implemented and verified.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Whole-suite and whole-pipeline verification, plus the
project's required handoff-contract writes.

- [x] T017 Run `cd backend && uv run pytest tests/ -q` — confirm no new
      failures vs. `main` (isolate and re-run any DB-contention or
      LLM-sampling-flaky failures per `CLAUDE.md`'s documented gotchas
      before treating as a regression) — 350/351 passed; the 1 failure
      (`test_warmer_raises_mean_warmth_and_preserves_occasion`) reproduced
      as a PASS twice in isolation immediately after — confirmed LLM-sampling
      flakiness per the documented gotcha, not a regression
- [x] T018 [P] Run `cd backend && uv run ruff check . && uv run ruff format .`
      — clean on every file this feature touches (pre-existing unrelated
      lint debt in notebooks/ and external/trends.py left untouched, out of
      scope)
- [x] T019 Run `cd backend && uv run python -m whattowear.eval.harness`;
      compare `backend/artifacts/eval_runs/*.jsonl` against
      `docs/eval-baselines/pre-009/*.jsonl` per `quickstart.md` step 4 —
      `retrieval_recall` byte-identical on all 23 shared cases across all 3
      strategies (the post-009 `advanced` run also gained a 24th case, g17,
      previously missing from a flaky pre-009 run); `owned_only` 1.00 with
      zero diffs; 0 hallucinated items in both runs. Full comparison:
      `docs/eval-baselines/pre-009/COMPARISON.md`
- [x] T020 Ran the manual sanity check and recorded the concrete before/after
      `color_harmony` score+reason for the tonal and clashing outfits — see
      `docs/eval-baselines/pre-009/COMPARISON.md`'s "Color-harmony fix"
      section (this is the deliverable's Task 5 evidence)
- [x] T021 Write state back per `CLAUDE.md`'s handoff contract: update
      `docs/SDD-HANDOFF.md` (feature table + current state),
      `CLAUDE.md`'s "Current state" section, `docs/ai-v2-session-handoff.md`
      (mark 009 done, note whatever the owner's directive says comes next —
      010/011), and mark this file's tasks `[X]`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Done.
- **Foundational (Phase 2)**: None — user stories can start immediately.
- **User Stories (Phase 3-6)**: Fully independent of each other (US1-US4
  touch disjoint functions; US1 and US4 share a file but not a region).
  Can be done in any order or in parallel; priority order (P1s first, then
  the P2) is the recommended sequence.
- **Polish (Phase 7)**: Depends on all four user stories being complete —
  it's the combined verification, not per-story.

### Within Each User Story

- Tests before implementation (write first, confirm they fail, then
  implement until green).
- Each story's implementation task depends only on that story's own test
  task, never on another story.

### Parallel Opportunities

- T003 and T004 (US1 tests) can run in parallel — different files.
- All four stories' *test-writing* tasks (T003/T004, T008, T011, T014) can
  run in parallel with each other — no shared files, no shared state.
- US2 and US3 are fully independent of US1/US4's `colors.py` changes and of
  each other — can be implemented in any order relative to them.

---

## Parallel Example: Writing all four stories' tests up front

```bash
Task: "Add hex_to_hsl unit tests to backend/tests/unit/test_colors.py"
Task: "Rewrite backend/tests/unit/scoring/test_color_harmony.py"
Task: "Update test_combine.py's default-strategy test"
Task: "Add wardrobe_retrieval sort-before-cap test to test_graph.py"
Task: "Add nearest_names teal test to test_colors.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

US1 (color-harmony rewrite) is both the highest-priority story and the
deliverable's headline bug story — complete Phase 3, validate independently
(T007), and the certification-relevant narrative already holds even before
US2-US4 land.

### Incremental Delivery

1. Phase 1 (done) → Phase 3 (US1) → validate → this alone is demoable.
2. Add US2 (Phase 4) → validate.
3. Add US3 (Phase 5) → validate.
4. Add US4 (Phase 6) → validate.
5. Phase 7: full-suite + eval-gate verification, then write state back.

## Notes

- [P] tasks touch different files or disjoint regions of the same file.
- Commit after each user story's checkpoint, not after every task.
- Per the project's global rule: never weaken a test that encodes wrong
  behavior — replace it (applies to T004's deleted test and T008's rewritten
  one).
- T017-T019 constitute the constitution's mandatory no-regression gate for
  any change touching scoring/retrieval — do not skip before merging.
