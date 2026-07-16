---

description: "Task list for Styling Agent (002)"
---

# Tasks: Styling Agent

**Input**: Design documents from `/specs/002-styling-agent/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/suggest.md](./contracts/suggest.md), [quickstart.md](./quickstart.md)

**Tests**: Included. Not requested verbatim by the spec, but the project
constitution's Quality Bar mandates unit tests for deterministic logic, and
this feature is almost entirely deterministic pruning/scoring/ranking logic
(constitution Principle II, V).

**Organization**: This project ships Feature 002 as **four independently
mergeable delivery phases** (spec.md "Delivery Phases", plan.md Summary) rather
than the template's default one-phase-per-user-story layout, because the
phases were decided ahead of the spec for branch-per-phase-merge reasons (see
root `CLAUDE.md` "Branch strategy note (002 only)"). Each phase below still
carries `[USx]` labels per task for story-coverage traceability; Phase 3 is
where US2 and US3's ranking both become user-observable (US3's scoring math is
independently unit-tested in Phase 2, but has no endpoint to be tested through
until Phase 3 ships `/suggest`).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Maps the task to US1/US2/US3/US4
- File paths are relative to the repo root

---

## Phase 1: Essentials — auth gate + unit-test backfill (Priority: P1, US1) ✅ DONE

**Goal**: Close the live `/recommend` cross-user leak and backfill unit tests for
the pre-existing deterministic pipeline, so later phases build on a tested,
correctly-scoped base.

**Independent Test**: Call `/recommend` with no bearer token → 401, no closet
data returned. Call it as user A with user B's id smuggled in the body → only
A's closet is read. Existing deterministic modules have passing unit tests.

**Status**: Implemented on this branch (`002-styling-agent`) before this
spec/plan/tasks cycle was run; grounded here retroactively so the completed
work has spec/task traceability rather than sitting outside the workflow.

- [X] T001 [US1] Auth-gate `POST /recommend` behind `get_current_user_id` in `backend/src/whattowear/api.py` — `RecommendRequest` no longer accepts `user_id` in the body; the endpoint now takes `user_id: str = Depends(get_current_user_id)` and passes the verified `sub` claim to `run_pipeline()`
- [X] T002 [P] [US1] Unit tests for `colors.py` (hex validation/normalization, palette lookup, nearest-name, WCAG contrast ratio/hint) in `backend/tests/unit/test_colors.py`
- [X] T003 [P] [US1] Unit tests for `categories.py` (group_of, is_core/is_accessory, unknown-category-defaults-to-accessory) in `backend/tests/unit/test_categories.py`
- [X] T004 [P] [US1] Unit tests for `pipeline/cite.py` (cited_rule_ids, owned_only, all_cites_grounded, every_choice_cites, build_result, render_text) in `backend/tests/unit/test_cite.py`
- [X] T005 [P] [US1] Unit tests for `pipeline/query_builder.py` (route's L1/L4-always + L3-if-season + L2-never rule, naive_query, l3_query) in `backend/tests/unit/test_query_builder.py`
- [X] T006 [P] [US1] Unit tests for `eval/properties.py` (owned_only, weather_appropriate, occasion_fit, respects_exclusions, check_outfit) in `backend/tests/unit/test_eval_properties.py`
- [X] T007 [US1] Integration test for the `/recommend` auth gate (401 with no token; JWT `sub` drives the pipeline, not a body-supplied `user_id`) in `backend/tests/integration/test_recommend_auth.py` (depends on T001)

**Checkpoint**: US1 fully satisfied — SC-001, SC-009. No retrieval/generation
behavior changed, so no eval-gate re-run required for this phase (constitution
Principle I's trigger condition — "after any change touching
retrieval/generation" — doesn't fire here).

---

## Phase 2: Foundational — deterministic scoring package (blocks US2's ranking, delivers US3's core)

**Purpose**: The four dimension scorers plus the swappable combination strategy
(FR-009a) that Phase 3's `score_and_rank` graph node depends on for ranking, and
that US3 promises to the user. Built and unit-tested standalone before the graph
exists, per constitution Principle V (scoring functions are eval metrics,
written as code first).

**⚠️ CRITICAL**: Phase 3's `score_and_rank` node cannot be implemented until this
phase is complete.

- [X] T008 [P] Create `backend/src/whattowear/scoring/__init__.py` package skeleton
- [X] T009 [P] Add `DimensionScore` Pydantic model (`dimension` literal, `value: float 0-1`, `reason: str`) to `backend/src/whattowear/schema.py` per data-model.md
- [X] T010 [US3] Add `ScoredOutfit` Pydantic model (extends `Outfit` with `scores: list[DimensionScore]` exactly-4 and `rank_score: float`) to `backend/src/whattowear/schema.py` per data-model.md (depends on T009)
- [X] T011 [P] [US3] Implement `score(items, ctx) -> DimensionScore` for color harmony in `backend/src/whattowear/scoring/color_harmony.py`, reusing `colors.contrast_ratio`/`colors.nearest_names` (no reimplementation of WCAG math)
- [X] T012 [P] [US3] Implement `score(items, ctx) -> DimensionScore` for formality coherence in `backend/src/whattowear/scoring/formality_coherence.py`, reusing `schema.FORMALITY_ORDER`
- [X] T013 [P] [US3] Implement `score(items, ctx) -> DimensionScore` for weather fitness in `backend/src/whattowear/scoring/weather_fitness.py`, reusing `categories.group_of` and the same warmth/outerwear reasoning `eval/properties.weather_appropriate` already encodes (import/reuse, don't fork the logic in two places)
- [X] T014 [P] [US3] Implement `score(items, ctx) -> DimensionScore` for silhouette balance in `backend/src/whattowear/scoring/silhouette_balance.py` — general proportion/balance principles only, no body-shape personalization (spec Future Work)
- [X] T015 [US3] Implement `backend/src/whattowear/scoring/combine.py`: `Strategy = Callable[[list[DimensionScore]], float]` typedef, `EQUAL_WEIGHTED_AVERAGE` default strategy, one documented alternative (fit-first lexicographic: weather+formality first, color+silhouette as tiebreak), and `rank_outfits(outfits, strategy=EQUAL_WEIGHTED_AVERAGE)` — the one call site Phase 3's `score_and_rank` node uses (FR-009a) (depends on T009)
- [X] T016 [P] [US3] Unit tests for `color_harmony.score` (a high-contrast pair scores higher than a clashing/low-signal pair; reason string present; re-scoring the same outfit and context twice is identical, FR-009) in `backend/tests/unit/scoring/test_color_harmony.py` (depends on T011)
- [X] T017 [P] [US3] Unit tests for `formality_coherence.score` (a formality-consistent outfit scores higher than a mismatched one; re-scoring the same outfit and context twice is identical, FR-009) in `backend/tests/unit/scoring/test_formality_coherence.py` (depends on T012)
- [X] T018 [P] [US3] Unit tests for `weather_fitness.score` (cold context + no outerwear scores lower than cold context + outerwear; re-scoring the same outfit and context twice is identical, FR-009) in `backend/tests/unit/scoring/test_weather_fitness.py` (depends on T013)
- [X] T019 [P] [US3] Unit tests for `silhouette_balance.score` (deterministic, reason present, no body-shape input required; re-scoring the same outfit and context twice is identical, FR-009) in `backend/tests/unit/scoring/test_silhouette_balance.py` (depends on T014)
- [X] T020 [US3] Unit tests for `combine.py` — default strategy is a true average, the alternative strategy is genuinely different on a constructed example, `rank_outfits` orders descending by combined score, and re-running the same input twice is byte-identical (SC-005) — in `backend/tests/unit/scoring/test_combine.py` (depends on T015)
- [X] T021 Import `scoring/*.score` and `scoring/combine.rank_outfits` unchanged into `backend/src/whattowear/eval/harness.py` as the reused, non-reimplemented metric functions (constitution Principle V) (depends on T011-T015)
- [X] T022 Re-run the eval no-regression gate — Phase 2 adds scoring only, touches neither retrieval nor generation, so `retrieval_recall` must be exactly unchanged from `backend/artifacts/eval_runs/` (depends on T021)

**Checkpoint**: Scoring package fully implemented and unit-tested in isolation —
US3's scoring math is done; it has no endpoint to be observed through until
Phase 3.

---

## Phase 3: Graph + real selection — `/suggest` (Priority: P1/P2, US2 + US3's ranking)

**Goal**: The pipeline becomes a LangGraph `StateGraph`; deterministic
pruning/combination/scoring (Phase 2's package) replaces any model-driven item
picking; `POST /suggest` (SSE) delivers grounded, scored outfit suggestions.
`/recommend` stays live only until `/suggest` is verified equivalent **and the
frontend (Feature 003, which didn't exist when this phase was first planned)
is confirmed cut over to it (T036a-d)**, then is retired within this same
phase (T037a) — see the type-sharing rationale there: `OutfitResult.outfits`
becomes `list[ScoredOutfit]` in this phase, and `/recommend`'s old code path
never populates scores, so the two endpoints cannot coexist past this phase
without a second result type nobody wants to maintain. **This phase now
includes a small amount of frontend work** (T036a-d) — a `/speckit.analyze`
finding, not in the original plan: the plan's "no frontend work this feature"
premise was true when written and is false now.

**Independent Test**: As a user with a closet that can dress the occasion,
`POST /suggest` returns an SSE stream ending in a `done` event with 3–5
`ScoredOutfit`s, each built only from owned items, each carrying all four
`DimensionScore`s and a `rank_score`, ordered by that score.

- [X] T023 Define `GraphState` (TypedDict: request fields, `Context`, `RetrievalResult`, candidate/generated outfits, `ScoredOutfit` list, `thread_id`) in `backend/src/whattowear/pipeline/graph.py` per data-model.md
- [X] T024 [P] [US2] `parse_request` node — normalizes the incoming `SuggestRequest` into `GraphState`; when `thread_id` is absent this is a plain new-request parse (refinement intent parsing is Phase 4) — in `backend/src/whattowear/pipeline/graph.py` (depends on T023)
- [X] T025 [P] [US2] `gather_context` node wrapping `pipeline/context_assembler.assemble_context` unchanged — in `backend/src/whattowear/pipeline/graph.py` (depends on T023)
- [X] T026 [P] [US2] `style_retrieval` node wrapping `pipeline/query_builder.route` + the existing KB retrieval call (`_retrieve` from `pipeline/run.py`) unchanged — in `backend/src/whattowear/pipeline/graph.py` (depends on T023)
- [X] T027 [US2] `build_query` node wrapping `pipeline/query_builder.naive_query`/`l3_query` unchanged — in `backend/src/whattowear/pipeline/graph.py` (depends on T023 — an independent function implementation, like the other nodes; only T032's wiring encodes actual node order)
- [X] T028 [US2] `wardrobe_retrieval` node — prunes the closet by hard constraints (warmth band, formality band, season, reusing `eval/properties.py`'s predicates) **before** combining, caps candidates at k=8 per slot (FR-014) — in `backend/src/whattowear/pipeline/graph.py` (depends on T023)
- [X] T029 [US2] `generate_outfits` node wrapping `pipeline/generator.generate` unchanged for item assembly + rationale text; an outfit missing a required slot is dropped from the candidate set, never filled from the catalog (FR-011, no substitution this feature) — in `backend/src/whattowear/pipeline/graph.py` (depends on T028)
- [X] T030 [US2] [US3] `score_and_rank` node — calls each `scoring/*.score()` per candidate outfit, assembles `ScoredOutfit.scores` (all 4, FR-008), calls `scoring/combine.rank_outfits` for `rank_score` and final order — in `backend/src/whattowear/pipeline/graph.py` (depends on T029, T015)
- [X] T031 [US2] `explain` node wrapping `pipeline/cite.build_result` unchanged, extended to carry `ScoredOutfit` instead of `Outfit` — in `backend/src/whattowear/pipeline/graph.py` (depends on T030)
- [X] T032 [US2] Assemble the `StateGraph`: wire T024→T025→T026→T027→T028→T029→T030→T031 as linear edges, compile with `memory.checkpointer` (Phase 4 will swap its backend, not this wiring) — in `backend/src/whattowear/pipeline/graph.py` (depends on T024-T031)
- [X] T032a Extend `eval/harness.py` to run golden-set cases through the compiled graph (`pipeline/graph.py`) **instead of** `pipeline.run.run_pipeline` (not alongside — `run.py` is retired at T037a, so the harness has exactly one entrypoint after this phase, not two to keep in sync), and add graph-specific entries to `data/golden_set.yaml` covering multi-outfit, scored, ranked `/suggest` output — closes the constitution Quality Bar gate ("LLM-dependent paths require an entry in `data/golden_set.yaml`") for the new path, and is what actually lets SC-003/SC-004/SC-005/SC-007 be measured rather than just asserted (depends on T032)
- [X] T033 [US2] Add `SuggestRequest` Pydantic model (no `user_id` field, per contracts/suggest.md) to `backend/src/whattowear/schema.py`
- [X] T034 [US2] Implement `POST /suggest` — auth-gated identically to `/recommend` (`get_current_user_id`, FR-001), invokes the compiled graph, streams `event: outfit` chunks then `event: done` via FastAPI `StreamingResponse` (no new SSE dependency, research.md §6) — in `backend/src/whattowear/api.py` (depends on T032, T033)
- [X] T035 [P] [US2] Unit tests for the `wardrobe_retrieval` node's pruning/cap behavior (hard-constraint filtering excludes out-of-band items; candidate count never exceeds k=8 per slot regardless of closet size) in `backend/tests/unit/pipeline/test_graph.py` (depends on T028)
- [X] T036 [US2] [US3] Integration test for `POST /suggest`: 3–5 outfits for a well-stocked closet, fewer + `note` for an undersized one (FR-002), every item id owned by the requester (FR-003, SC-002), every outfit carries all 4 `DimensionScore`s plus `rank_score`, and outfits are returned in descending `rank_score` order (FR-008, US3 Acceptance Scenario 2) — in `backend/tests/integration/test_suggest.py` (depends on T034)
- [X] T037 Re-run the eval no-regression gate — Phase 3 wires retrieval/generation into the graph via unchanged functions (constitution Principle I); `retrieval_recall` must match `backend/artifacts/eval_runs/` (depends on T034, T032a)
- [X] T036a [P] [US2] [US3] SSE-consumption helper in `frontend/lib/api-client.ts` — a new function alongside `apiFetch` (not a modification to it; every other endpoint depends on `apiFetch` staying simple). Browsers' native `EventSource` only supports `GET` and `/suggest` is `POST`, so this must be a hand-rolled parser over `fetch()`'s streaming response body (`ReadableStream` + `TextDecoder`, splitting on `event:`/`data:` lines), not `EventSource` — a `/speckit.analyze` finding: nothing in the frontend can currently consume an SSE response at all (depends on T034)
- [X] T036b [P] [US2] Regenerate `frontend/lib/api-types.ts` via `npm run fetch:openapi` against a locally running backend with `/suggest` live, so `SuggestRequest`/`ScoredOutfit`/`DimensionScore` exist on the frontend side (constitution Principle VII, same mechanism Feature 003 established) (depends on T033, T034)
- [X] T036c [US2] [US3] Cut the frontend over to `/suggest`: `frontend/app/suggest/page.tsx` calls `/suggest` via T036a's helper instead of `POST /recommend` (consume the `done` event only — no progressive per-outfit streaming UI, that's unscoped new product work, not part of this fix); `frontend/components/SuggestionResult.tsx` renders the four `DimensionScore`s + `rank_score` per outfit, closing the gap between US3's API-level score data (T030) and its actual product promise ("the user sees a separate score") (depends on T036a, T036b, T010)
- [X] T036d [US2] [US3] Manual end-to-end verification: dev-server smoke test of the cut-over suggest flow against a locally running backend (same pattern Feature 003 used for its own frontend work) — confirms the live product actually still works before anything is deleted (depends on T036c)
- [X] T037a [US2] Retire `POST /recommend` and `pipeline/run.py` now that `eval/harness.py` runs golden-set cases through the graph (T032a), the no-regression gate is confirmed clean (T037), **and the frontend is confirmed cut over to `/suggest` (T036d)**: remove the endpoint and `RecommendRequest`/`RecommendResponse` from `backend/src/whattowear/api.py`, delete `backend/src/whattowear/pipeline/run.py`, delete `backend/tests/integration/test_recommend_auth.py` (its 401/JWT-`sub` coverage is subsumed by T036's `/suggest` integration test) — resolves the `OutfitResult.outfits: list[ScoredOutfit]` type-sharing question by removing the only caller that couldn't populate scores. **T036d is the gate that prevents this from breaking the live, deployed frontend** — a `/speckit.analyze` CRITICAL finding: the original task had no dependency on the frontend at all, and `frontend/` didn't exist when this task was first written (depends on T032a, T036, T037, T036d)

**Checkpoint**: US2 and US3 fully satisfied and observable end-to-end through
`/suggest`; `/recommend` retired, `/suggest` is the sole suggestion entrypoint.

---

## Phase 4: Refinement (Priority: P2, US4)

**Goal**: A user can ask for alternatives or refine with short follow-ups
("warmer", "less formal") on an existing thread, without restating the original
request; the original occasion and unstated constraints are preserved.

**Independent Test**: `POST /suggest` without `thread_id` to start a thread,
then `POST /suggest` with that `thread_id` and `occasion: "warmer"` — the new
outfits show higher average warmth while `context.occasion` in the response is
still the original occasion.

- [X] T038 Add `langgraph-checkpoint-postgres` to `backend/pyproject.toml`; `uv sync`
- [X] T039 Swap `memory/store.py`'s `checkpointer = InMemorySaver()` for a `PostgresSaver` against the existing `DATABASE_URL`, using that package's own setup/migration (no hand-rolled thread-state table, research.md §5) — in `backend/src/whattowear/memory/store.py` (depends on T038)
- [X] T040 [US4] Extend `parse_request` to distinguish a new request from a refinement: when `thread_id` is present, look up the `RefinementTurn` (checkpointer state: `original_context`, `last_result`, `refinement_deltas`) and interpret the utterance ("warmer"/"less formal"/"alternatives") against it rather than as a fresh occasion — in `backend/src/whattowear/pipeline/graph.py` (depends on T032, T039)
- [X] T041 [US4] Implement the "warmer"/"less formal" deltas: adjust the hard-constraint pruning bounds in `wardrobe_retrieval` (raise warmth floor / lower formality band) while keeping `original_context`'s occasion, mood, and other fields untouched (FR-013) — in `backend/src/whattowear/pipeline/graph.py` (depends on T040)
- [X] T042 [US4] Implement "give me alternatives" (FR-012): re-run `generate_outfits`/`score_and_rank` excluding the item-sets already present in `last_result` — in `backend/src/whattowear/pipeline/graph.py` (depends on T040)
- [X] T043 [US4] Handle an unsatisfiable refinement (FR-015): when no candidate improves on the requested dimension, return the best available `result` with a `note` explaining the request couldn't be fully satisfied — in `backend/src/whattowear/pipeline/graph.py` (depends on T041)
- [X] T044 [P] [US4] Unit tests for refinement-intent parsing ("warmer" → raised warmth floor, "less formal" → lowered formality band, "alternatives" → exclusion set, unsatisfiable case → note) in `backend/tests/unit/pipeline/test_graph.py` (depends on T040-T043)
- [X] T045 [US4] Integration test: start a thread, refine with "warmer", confirm preserved occasion + measurably higher average warmth (US4 Acceptance Scenario 1, SC-007); repeat for "less formal" and "alternatives" — in `backend/tests/integration/test_suggest_refinement.py` (depends on T041-T043)
- [X] T046 [FR-010, optional — "MAY"] Reported-only LLM judge score: compute and attach to the response for evaluation purposes, verify it never influences `rank_score` or ordering — in `backend/src/whattowear/eval/` (depends on T037)
- [ ] T047 Re-run the eval no-regression gate for Phase 4 (constitution Principle I) (depends on T045)

**Checkpoint**: All four user stories independently functional; feature
complete per spec.md.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T048 [P] `uv run ruff check` / format all new and modified files in `backend/`
- [ ] T049 Walk through `quickstart.md` end-to-end by hand for whichever phases have landed at merge time
- [ ] T050 [P] Per the handoff contract (root `CLAUDE.md` "Session workflow"): update `docs/SDD-HANDOFF.md`'s Feature 002 row/Step 3 and `CLAUDE.md`'s "Current state" section for the phase(s) just merged; mark this phase's tasks `[X]` in this file
- [ ] T050a [P] Backfill unit tests for `pipeline/context_assembler.py` (`assemble_context`'s weather-fallback chain: location resolves → weather lookup fails → falls back to `temp_c` → falls back to season-only; `OCCASION_FORMALITY` default lookup) in `backend/tests/unit/test_context_assembler.py` — closes a pre-existing gap (Feature 001's Known Debt list named `colors.py`/`cite.py`/`categories.py`/`query_builder.py`/`eval/properties.py` only) that FR-006 leans on but nothing in this feature previously covered

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (essentials, US1)**: ✅ done — no dependency on later phases
- **Phase 2 (foundational scoring)**: independent of Phase 1's specific changes; blocks Phase 3's `score_and_rank` node (T030 depends on T015)
- **Phase 3 (graph + `/suggest`, US2+US3)**: depends on Phase 2 completing (needs `scoring/combine.rank_outfits`); now also includes a frontend cutover (T036a-d, a `/speckit.analyze` finding — Feature 003's frontend didn't exist when this phase was originally planned) that must complete before `/recommend` retires (T037a) — Phase 4 has only one endpoint to extend
- **Phase 4 (refinement, US4)**: depends on Phase 3's compiled graph (T032) existing to extend, and on `/recommend` already being gone (T037a) so there's no second endpoint to also wire refinement into
- **Phase 5 (polish)**: runs after whichever phase is about to merge

### Critical wiring note (C1)

`score_and_rank` (T030) is the join point between the scoring package (Phase 2)
and the graph (Phase 3) — it is the only place `scoring/*.score()` and
`scoring/combine.rank_outfits` are called from request-handling code. Get this
wrong (e.g. reimplementing scoring inline in the graph node) and constitution
Principle V's "same functions in the harness" guarantee (T021) silently stops
holding.

### Parallel Opportunities

- Phase 2: T011–T014 (the four scorers) are fully independent files and can be
  built in parallel; their unit tests T016–T019 likewise.
- Phase 3: T024–T026 (parse_request, gather_context, style_retrieval) don't
  depend on each other's output within the same file edit, but all land in the
  same `graph.py` — treat as sequential edits to one file in practice despite
  the nominal independence.

## Parallel Example: Phase 2 scorers

```bash
Task: "Implement color_harmony.score() in backend/src/whattowear/scoring/color_harmony.py"
Task: "Implement formality_coherence.score() in backend/src/whattowear/scoring/formality_coherence.py"
Task: "Implement weather_fitness.score() in backend/src/whattowear/scoring/weather_fitness.py"
Task: "Implement silhouette_balance.score() in backend/src/whattowear/scoring/silhouette_balance.py"
```

## Implementation Strategy

### MVP scope

Phase 1 is already the smallest safe increment and is done. The next
merge-worthy increment is Phase 2 + Phase 3 together (US2 is the feature's
central promise per spec.md and cannot be demoed without US3's ranking, which
Phase 3 needs from Phase 2) — Phase 2 alone has no user-facing surface.

### Incremental Delivery

1. Phase 1 → merged (this branch, pending PR)
2. Phase 2 → scoring package merged, eval gate confirms no drift
3. Phase 3 → `/suggest` ships, US2+US3 demoable; eval gate re-run
4. Phase 4 → refinement ships, US4 demoable; eval gate re-run
5. Each phase's own PR per the branch strategy note in root `CLAUDE.md`

---

## Notes

- [P] tasks touch different files and have no incomplete dependencies
- Constitution Principle V is the thread through Phases 2–3: scoring functions
  are written once, imported unchanged into both the graph (T030) and the eval
  harness (T021) — never reimplemented in either caller
- FR-009a's swappable combination strategy is *not* a decision to finalize —
  `EQUAL_WEIGHTED_AVERAGE` ships as the default but `combine.py` existing as an
  isolated module is the point: comparing strategies is ongoing evaluation
  work, not a task to close out here
- Body shape and catalog substitution are explicitly out of scope this
  feature (spec Future Work) — no task above should reintroduce either
