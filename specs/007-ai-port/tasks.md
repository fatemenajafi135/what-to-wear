# Tasks: AI layer port

**Input**: Design documents from `/specs/007-ai-port/` · **Branch**: `feat/007-ai-port`

**Ordering note**: unlike a typical user-story-sliced feature, this port's sequencing is
dictated by the handoff brief §5 ("Order of work — follow it... sequence matters more here
than anywhere else in the project"), not by story priority alone — the pipeline is one
tightly-coupled dependency graph (leaves → scoring → retrieval → memory → external →
pipeline → eval), so every user story depends on most of the same phases. Phases below
follow that mandated order; `[US#]` labels record which story each phase primarily serves,
but do not imply the phases can be reordered by story priority the way an independent-slice
feature's tasks could be.

**One commit per task** (handoff §5.2) unless a task is explicitly a multi-file batch (e.g.
T059's whole-tree lint pass, which is inherently cross-cutting).

## Phase 1: Setup

- [ ] T001 Add AI-layer dependencies (`langgraph`, `langchain-core`, `langchain-litellm`, `langchain-openai`, `langchain-cohere`, `langchain-qdrant`, `qdrant-client`, `langsmith`, `tavily-python`, `pyyaml`, `psycopg_pool`) to `backend/pyproject.toml`; `uv sync`
- [ ] T002 [P] Extend `backend/src/whattowear/core/config.py` with AI Gateway / Qdrant / Cohere / Tavily / LangSmith settings fields (mirrors legacy `config.py`'s env vars, lazy via existing `Settings`/`get_settings()` pattern — no module-level client construction)
- [ ] T003 Create `backend/src/whattowear/ports.py` — `VectorStore`, `LLMClient`, `ClosetRepository` Protocols per `contracts/ports.md`
- [ ] T004 [P] Create `backend/src/whattowear/prompts/__init__.py` with `load_prompt(name) -> tuple[str, int]` per `contracts/prompt-front-matter.md`
- [ ] T005 [P] Copy `../app-legacy/backend/data/fixtures/wardrobe.json` → `backend/evals/fixtures/wardrobe.json` and `../app-legacy/backend/data/golden_set.yaml` → `backend/evals/golden_set.yaml` (tracked exception, constitution X)
- [ ] T006 Create `backend/src/whattowear/adapters/closet_fixture.py::FixtureClosetRepository` implementing `ClosetRepository` from `backend/evals/fixtures/wardrobe.json` (Research §5)
- [ ] T007 [P] Unit tests for T003/T006 in `backend/tests/unit/test_ports.py` and `backend/tests/unit/test_closet_fixture.py`

**Checkpoint**: `ports.py` compiles, fixture repository returns the 40-item wardrobe for any user id and as the catalog, `get_derivation_inputs` returns `([], [])`.

## Phase 2: Foundational (blocks every user story)

- [ ] T008 Port `schema.py` → `backend/src/whattowear/schema.py` (frozen taxonomy + contracts, unchanged) + `backend/tests/unit/test_schema.py`
- [ ] T009 [P] Port `colors.py` → `backend/src/whattowear/colors.py` + `backend/tests/unit/test_colors.py`
- [ ] T010 [P] Port `categories.py` → `backend/src/whattowear/categories.py` + `backend/tests/unit/test_categories.py`
- [ ] T011 Extend `backend/tests/unit/test_import_safety.py`'s parametrised list with `whattowear.schema`, `whattowear.colors`, `whattowear.categories`, `whattowear.ports`

**Checkpoint**: `env -i python3 -c "import whattowear.schema"` (and colors/categories/ports) succeed with zero env vars.

## Phase 3: `scoring/` package (US1, US4)

**Goal**: deterministic outfit scoring, importable and unit-tested standalone.
**Independent test**: `uv run pytest backend/tests/unit/test_scoring*.py` — all four dimension scorers + combine produce the same values as the legacy code on fixed inputs, no LLM call, no DB.

- [ ] T012 Create `backend/src/whattowear/scoring/properties.py` — move `owned_only`, `weather_appropriate`, `occasion_fit`, `respects_exclusions`, `check_outfit` from legacy `eval/properties.py` verbatim (Research §2) + `backend/tests/unit/test_scoring_properties.py`
- [ ] T013 [P] Port `scoring/color_harmony.py` + test
- [ ] T014 [P] Port `scoring/combine.py` + test
- [ ] T015 [P] Port `scoring/formality_coherence.py` + test
- [ ] T016 [P] Port `scoring/silhouette_balance.py` + test
- [ ] T017 Port `scoring/weather_fitness.py` — imports `scoring.properties.weather_appropriate`, not `eval.properties` (defect fix) + test
- [ ] T018 Port `scoring/__init__.py` (`rank_outfits`, `score_outfits`) + test

**Checkpoint**: `whattowear.scoring` imports with zero env vars; no `eval` import anywhere in `scoring/`. Extend `test_import_safety.py`'s parametrised list with every `scoring.*` module landed above (SC-003).

## Phase 4: `retrieval/` package (US1, US4)

**Goal**: three retrieval strategies (baseline/hybrid/advanced) against `ports.VectorStore`.
**Independent test**: unit tests with a stub `VectorStore` confirm each strategy's query-shaping logic without a real Qdrant connection.

- [ ] T019 Port `retrieval/base.py` (`RetrievalResult`) + test
- [ ] T020 [P] Port `retrieval/baseline.py` (naive dense, A/B control — keep per inventory Q5) + test
- [ ] T021 Port `retrieval/hybrid.py` (per-layer hybrid) + test
- [ ] T022 Port `retrieval/advanced.py` (hybrid + Cohere rerank via `core.config.get_reranker`) + test

**Checkpoint**: `whattowear.retrieval` imports with zero env vars; no `whattowear.kb` import at module load time (only inside functions that receive an injected `VectorStore`/KB object). Extend `test_import_safety.py` with every `retrieval.*` module landed above (SC-003).

## Phase 5: `memory/` package (US1, US4) — DB coupling fix #2 of 3

**Goal**: preference derivation and the LangGraph checkpointer, with the DB read routed through `ClosetRepository`.
**Independent test**: `memory.store.get_profile(user_id)` returns `None`/empty against a `FixtureClosetRepository`, with no `whattowear.core.db` import at module scope.

- [ ] T023 Port `memory/preferences.py` (pure signal derivation) + test
- [ ] T024 Port `memory/store.py` — replace `from ..db import SessionLocal` + `crud.get_derivation_inputs` with an injected `ClosetRepository.get_derivation_inputs` (Research §1); leave `get_checkpointer()`'s raw `DATABASE_URL_DIRECT`/`DATABASE_URL` psycopg pool construction as-is (LangGraph's own storage backend, not a `SessionLocal`/ORM concern) + test with `FixtureClosetRepository`

**Checkpoint**: no `from ..db import` or `from .. import crud` anywhere in `memory/`. Extend `test_import_safety.py` with `memory.preferences`, `memory.store` (SC-003).

## Phase 6: `external/` package (US1)

**Goal**: weather lookup (no key) and trend search + distillation, prompt extracted.
**Independent test**: `weather.py` unit tests against a stubbed HTTP client; `trends.py` unit test against a recorded Tavily fixture, no live call.

- [ ] T025 [P] Port `external/weather.py` (Open-Meteo geocode + forecast) + test
- [ ] T026 Port `external/trends.py` — extract `_DISTILL_PROMPT` to `prompts/trends_distill.md` (`load_prompt("trends_distill")`) + test against a recorded fixture response

**Checkpoint**: no inline prompt string remains in `trends.py`. Extend `test_import_safety.py` with `external.weather`, `external.trends` (SC-003).

## Phase 7: `pipeline/` package (US1, US2, US4) — DB coupling fix #1 and #3 of 3, docstring fix

**Goal**: the full LangGraph styling pipeline, both grounded and engine paths, zero direct DB/eval imports.
**Independent test**: `build_graph()`/`compile_graph()` succeed with an injected `ClosetRepository` + stub `LLMClient`/`VectorStore`; no live LLM call in the test.

- [ ] T027 Port `pipeline/context_assembler.py` — replace `load_wardrobe`'s `from ..db import SessionLocal` + `crud.list_wardrobe_items` with an injected `ClosetRepository.list_wardrobe_items` (Research §1) + test
- [ ] T028 [P] Port `pipeline/query_builder.py` + test
- [ ] T029 [P] Port `pipeline/validity.py` + test
- [ ] T030 [P] Port `pipeline/grounding.py` + test
- [ ] T031 [P] Port `pipeline/cite.py` + test
- [ ] T032 [P] Port `pipeline/cache.py` + test
- [ ] T033 Port `pipeline/generator.py` — extract `SYSTEM_PROMPT` to `prompts/generator_system.md` + test
- [ ] T034 Port `pipeline/engine.py` — extract `_ENGINE_SYSTEM_PROMPT` to `prompts/engine_system.md` + test
- [ ] T035 Port `pipeline/graph.py` — replace `from ..db import SessionLocal` in `verify_grounding` with injected `ClosetRepository.list_catalog_items` (Research §1); replace `from ..eval.properties import weather_appropriate` with `from ..scoring.properties import weather_appropriate` (Research §2); correct the module docstring and `engine_enumerate_and_score`'s docstring per Research §3 — do not carry forward "the LLM never ranks" unqualified + test

**Checkpoint**: `whattowear.pipeline.graph` imports with zero env vars; no `from ..db import` or `from ..eval` anywhere under `pipeline/`. Extend `test_import_safety.py` with every `pipeline.*` module landed above (SC-003).

## Phase 8: `vision.py` (keep — Feature 003 will call it, out of this feature's scope to wire)

- [ ] T036 Port `vision.py` — extract `SYSTEM_PROMPT` to `prompts/vision_system.md` + test; extend `test_import_safety.py` with `whattowear.vision` (SC-003)

## Phase 9: `eval/` package — `src/whattowear/eval/` (US4)

**Goal**: the golden-set runner, ported to use `ClosetRepository` injection instead of a hardcoded DB-backed baseline user.

- [ ] T037 Port `eval/golden_set.py` (loads `backend/evals/golden_set.yaml`) + test
- [ ] T038 Port `eval/properties.py` as a thin re-export of `scoring.properties` (explicit `__all__`, Research §2)
- [ ] T039 Port `eval/judge.py` — extract `_PROMPT` to `prompts/judge.md` + test
- [ ] T040 Port `eval/harness.py` — inject `FixtureClosetRepository` (via `ports.py`) instead of relying on `crud.EVAL_BASELINE_USER_ID` + a live DB session; add `prompt_versions: dict[str, int]` to each JSONL row (data-model.md)
- [ ] T041 [P] Port `eval/test_users.py` (manual persona tool, UNREF — no automated test required, `__main__`-guarded)
- [ ] T042 [P] Port `eval/vision_harness.py` (UNREF — golden-case check for photo → attributes)

**Checkpoint**: `whattowear.eval.harness` imports and its `run_case` executes end-to-end against `FixtureClosetRepository`, with zero real DB connection required. Extend `test_import_safety.py` with every `eval.*` module landed above (SC-003).

## Phase 10: Evals running against ported modules — GATE (US4)

Per handoff §5.3: "Get the evals running against the ported modules before improving
anything... you cannot prove a refactor is safe if the measurement does not run yet." This
is a smoke checkpoint, not yet the full baseline comparison (that's Phase 15, after ingestion
gives retrieval something real to retrieve).

- [ ] T043 Run `uv run python -m whattowear.eval.harness --strategies advanced --limit 3` against an in-memory/sample Qdrant collection; confirm the graph executes end-to-end (both `--approach grounded` and `--approach engine`) without error, before any further module is touched

**STOP if T043 fails.** Do not proceed to Phase 11 improvements until the ported pipeline runs.

## Phase 11: `ingest/` package + corpus manifest (US3)

- [ ] T044 [P] Port `ingest/loaders.py` + test
- [ ] T045 [P] Port `ingest/chunkers.py` + test
- [ ] T046 [P] Port `ingest/wiki_refine.py` (CLI tool, UNREF, kept as a tool outside the service)
- [ ] T047 Create `infra/corpus.yaml` from `../app-legacy/backend/data/kb/manifest.yaml` per `data-model.md`'s schema (adds `path` relative to `$CORPUS_LOCAL_DIR`, `sha256` populated on first ingest); carry forward `want-later` entries (Black tie, Cocktail attire, Semi-formal wear) unchanged
- [ ] T048 Port `ingest/build_kb.py` — read `infra/corpus.yaml` + `CORPUS_LOCAL_DIR` instead of `data/kb/manifest.yaml`; build against `ports.VectorStore`
- [ ] T049 Create `backend/src/whattowear/ingest/cli.py` — idempotent-by-content-hash CLI entry point (FR-011); never an HTTP endpoint
- [ ] T050 Port `kb.py` (process-wide KB singleton) — uses `ingest.build_kb` + `ports.VectorStore`

**Checkpoint**: `uv run python -m whattowear.ingest.cli --help` runs with zero other env vars set beyond what argparse needs to print help. Extend `test_import_safety.py` with every `ingest.*` module + `whattowear.kb` (SC-003).

## Phase 12: `backend/evals` second `uv` project (US4)

- [ ] T051 Create `backend/evals/pyproject.toml` (pinned `langchain-community==0.3.31`, `package = false`) + copy `common.py`, `judge.py`, `score_ragas.py` from legacy, adjusted only for the new JSONL row shape (`prompt_versions`) if `score_ragas.py` enumerates row keys explicitly
- [ ] T052 Verify isolation per `quickstart.md`: `backend/`'s own `uv sync` never resolves `langchain-community==0.3.31`

## Phase 13: Qdrant index build (US3)

- [ ] T053 Run the ingestion CLI (T049) against `../w2w-corpus/` into the local Qdrant container; verify collection point count matches chunk count and both payload indexes (`metadata.layer`, `metadata.granularity`) exist
- [ ] T054 Re-run the CLI with no source changes; confirm zero re-embedding (content hash match) — SC-005

## Phase 14: Import-linter contract extension

- [ ] T055 Add `pipeline`, `retrieval`, `scoring`, `memory`, `ingest` to `backend/.importlinter`'s `source_modules`; run `uv run lint-imports` clean

## Phase 15: The eval gate — headline acceptance bar (US1, US2, US4)

- [ ] T056 Run the full 24-case golden set, `--approach grounded --strategies advanced`; capture `backend/artifacts/eval_runs/advanced.jsonl` + printed summary
- [ ] T057 Run the full 24-case golden set, `--approach engine --strategies advanced`; capture `backend/artifacts/eval_runs/advanced-engine.jsonl` + printed summary
- [ ] T058 Compare both runs against `../app-legacy/docs/eval-baselines/010-engine/COMPARISON.md` metric by metric; write the comparison into the final report (not averaged, every delta explained)

## Phase 16: Polish & cross-cutting

- [ ] T059 `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, `uv run pytest`, `uv run lint-imports` — all clean across all of `backend/`; additionally confirm FR-016 (no live LLM/embedding/rerank/web-search call in CI) by grepping `tests/` for un-mocked gateway/Tavily/Cohere client construction
- [ ] T060 Reconcile `backend/.env.example` against every env var actually read (no missed/no unused entries)
- [ ] T061 Write the final report: what was ported vs. improved vs. deliberately left alone, the eval comparison table, unmet Constitution Check gates, and any decision the inventory didn't cover (Research §5's fixture-repository call, in particular); confirm via `git status`/`git diff --stat` that no path under `$CORPUS_LOCAL_DIR` was ever staged (SC-006)

## Dependencies

Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8 → Phase 9 →
Phase 10 (gate) → Phase 11 → Phase 12 → Phase 13 → Phase 14 → Phase 15 → Phase 16.
Within a phase, `[P]`-marked tasks touch disjoint files and can run in parallel; unmarked
tasks either share a file with a preceding task in the same phase or depend on it directly
(e.g. T017 depends on T012's `scoring/properties.py` existing).

## Suggested MVP scope

Phases 1–7 plus T043 (Phase 10's smoke gate) constitute the smallest slice that proves the
grounded pipeline (US1) runs end-to-end on ported code. Phases 8–9 add the engine path's
supporting pieces and the eval harness itself; Phase 15 is not optional for this feature —
it is the feature's actual acceptance gate, not a stretch goal.
