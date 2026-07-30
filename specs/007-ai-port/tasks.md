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

- [x] T001 Add AI-layer dependencies (`langgraph`, `langchain-core`, `langchain-litellm`, `langchain-openai`, `langchain-cohere`, `langchain-qdrant`, `qdrant-client`, `langsmith`, `tavily-python`, `pyyaml`, `psycopg_pool`) to `backend/pyproject.toml`; `uv sync`
- [x] T002 [P] Extend `backend/src/whattowear/core/config.py` with AI Gateway / Qdrant / Cohere / Tavily / LangSmith settings fields (mirrors legacy `config.py`'s env vars, lazy via existing `Settings`/`get_settings()` pattern — no module-level client construction); create `backend/src/whattowear/adapters/llm_gateway.py` with `get_chat_model`/`get_judge_model`/`get_embeddings`/`get_reranker` factories (legacy `config.py`'s factory half, split out so `core/config.py` stays data-only — the factories are a concrete `ports.LLMClient` binding, which belongs in `adapters/` alongside `closet_fixture.py`)
- [x] T003 Create `backend/src/whattowear/ports.py` — `VectorStore`, `LLMClient`, `ClosetRepository` Protocols per `contracts/ports.md`
- [x] T004 [P] Create `backend/src/whattowear/prompts/__init__.py` with `load_prompt(name) -> tuple[str, int]` per `contracts/prompt-front-matter.md`
- [x] T005 [P] Copy `../app-legacy/backend/data/fixtures/wardrobe.json` → `backend/evals/fixtures/wardrobe.json` (40 items) and `../app-legacy/backend/data/golden_set.yaml` → `backend/evals/golden_set.yaml` (24 cases, tracked exception, constitution X)
- [x] T006 Create `backend/src/whattowear/adapters/closet_fixture.py::FixtureClosetRepository` implementing `ClosetRepository` from `backend/evals/fixtures/wardrobe.json` (Research §5) — `FeedbackRecord` deferred to `TYPE_CHECKING` so this lands without waiting on Phase 5
- [x] T007 [P] Unit tests for T003 in `backend/tests/unit/test_ports.py` (structural Protocol conformance) + `backend/tests/unit/test_llm_gateway.py` (factory error paths). `test_closet_fixture.py` deferred to right after T008 lands — `FixtureClosetRepository.list_wardrobe_items` needs a real `WardrobeItem` to construct against, which doesn't exist until `schema.py` ports.

**Checkpoint**: `ports.py`, `adapters/llm_gateway.py`, `adapters/closet_fixture.py`, `prompts/__init__.py` all import with zero env vars (verified — `test_import_safety.py` extended). `uv run ruff check .`, `ruff format --check .`, `uv run pytest` all clean (15 passed). `mypy` has 4 expected `import-untyped` errors on `schema`/`memory.preferences` — both don't exist until Phase 2/5, re-verify at T059.

## Phase 2: Foundational (blocks every user story)

- [x] T008 Port `schema.py` → `backend/src/whattowear/schema.py` (frozen taxonomy + contracts; ported whole per inventory's "keep" verdict, not trimmed to only what 007's own modules import — it's the shared contract file future features 003/004/006 need too; only mechanical change is `Optional[X]` → `X | None` to match project convention) + `backend/tests/unit/test_schema.py` (new — module never had one)
- [x] T009 [P] Port `colors.py` → `backend/src/whattowear/colors.py` (unchanged) + `backend/tests/unit/test_colors.py` (ported from legacy unchanged — already thorough)
- [x] T010 [P] Port `categories.py` → `backend/src/whattowear/categories.py` (unchanged) + `backend/tests/unit/test_categories.py` (ported from legacy unchanged)
- [x] T011 Extend `backend/tests/unit/test_import_safety.py`'s parametrised list with `whattowear.schema`, `whattowear.colors`, `whattowear.categories`, `whattowear.adapters.closet_fixture` (`whattowear.ports` was already added in T007). Also completed `test_closet_fixture.py` (deferred from T007 — needed `WardrobeItem` to exist).

**Checkpoint**: verified — `env -i python3 -c "import whattowear.schema"` (colors/categories/closet_fixture) all succeed with zero env vars (11/11 import-safety cases pass). `mypy src` now clean on schema/colors/categories/closet_fixture (only remaining errors are the expected `memory.preferences` not-yet-ported ones). 86 unit tests pass, `ruff`/`ruff format` clean.

## Phase 3: `scoring/` package (US1, US4)

**Goal**: deterministic outfit scoring, importable and unit-tested standalone.
**Independent test**: `uv run pytest backend/tests/unit/test_scoring*.py` — all four dimension scorers + combine produce the same values as the legacy code on fixed inputs, no LLM call, no DB.

- [x] T012 Create `backend/src/whattowear/scoring/properties.py` — move `owned_only`, `weather_appropriate`, `occasion_fit`, `respects_exclusions`, `check_outfit` from legacy `eval/properties.py` verbatim (Research §2) + `backend/tests/unit/scoring/test_properties.py` (ported from legacy `test_eval_properties.py`, import updated)
- [x] T013 [P] Port `scoring/color_harmony.py` (unchanged — three evaluated iterations, verified all 12 legacy tests pass) + test
- [x] T014 [P] Port `scoring/combine.py` (unchanged) + test
- [x] T015 [P] Port `scoring/formality_coherence.py` (unchanged) + test
- [x] T016 [P] Port `scoring/silhouette_balance.py` (unchanged) + test
- [x] T017 Port `scoring/weather_fitness.py` — imports `scoring.properties.weather_appropriate`, not `eval.properties` (defect fix) + test
- [x] T018 Port `scoring/__init__.py` (`rank_outfits`, `score_outfits`) — improved: `_GenOutfitLike.rationale` now typed `list[_RationaleLike]` instead of bare `list` (mypy strict mode caught this was previously untyped); `Iterable`/`Callable` moved to `collections.abc` per project convention. New test — `score_outfits` never had a direct unit test in the legacy suite despite 2 call sites.

**Checkpoint**: verified — `whattowear.scoring` (+ all 6 submodules) import with zero env vars (18/18 import-safety cases pass). No `eval` import anywhere in `scoring/` (grepped). 49 scoring tests pass, `ruff`/`ruff format` clean, `mypy` clean except the expected `memory.preferences` gap (Phase 5).

## Phase 4: `retrieval/` package (US1, US4)

**Goal**: three retrieval strategies (baseline/hybrid/advanced) against `ports.VectorStore`.
**Independent test**: unit tests with a stub `VectorStore` confirm each strategy's query-shaping logic without a real Qdrant connection.

- [x] T019 Port `retrieval/base.py` (`RetrievalResult`, unchanged) + test (new — never had one despite 11 refs)
- [x] T020 [P] Port `retrieval/baseline.py` (naive dense, A/B control — keep per inventory Q5; `KnowledgeBase` type deferred to `TYPE_CHECKING`, same pattern as `ports.py` — `kb.py` doesn't land until Phase 11) + test (new)
- [x] T021 Port `retrieval/hybrid.py` (per-layer hybrid, unchanged; `..logging_utils.get_logger` replaced with stdlib `logging.getLogger(__name__)` — `logging_utils.py` isn't ported this feature, see Phase 11 note, and this one call site didn't need the wrapper) + test (ported; `TestRetrieveL3Live`'s 4 cases skipped — need `external.trends`, Phase 6)
- [x] T022 Port `retrieval/advanced.py` (hybrid + Cohere rerank via `adapters.llm_gateway.get_reranker`, not `core.config` — factories live in `adapters/`, T002) + test

**Checkpoint**: verified — all 4 modules import with zero env vars (22/22 import-safety cases pass). 16 passed / 4 skipped (pending Phase 6) in `tests/unit/retrieval/`. `ruff`/`ruff format` clean. `mypy` clean except expected `whattowear.kb` (Phase 11) and `whattowear.external.trends` (Phase 6) gaps.

**Checkpoint**: `whattowear.retrieval` imports with zero env vars; no `whattowear.kb` import at module load time (only inside functions that receive an injected `VectorStore`/KB object). Extend `test_import_safety.py` with every `retrieval.*` module landed above (SC-003).

## Phase 5: `memory/` package (US1, US4) — DB coupling fix #2 of 3

**Goal**: preference derivation and the LangGraph checkpointer, with the DB read routed through `ClosetRepository`.
**Independent test**: `memory.store.get_profile(user_id)` returns `None`/empty against a `FixtureClosetRepository`, with no `whattowear.core.db` import at module scope.

- [x] T023 Port `memory/preferences.py` (pure signal derivation, unchanged logic; `key_of` param now properly typed `Callable[[ItemSnapshot], list[str]]` — was untyped in legacy) + test (new — never had one)
- [x] T024 Port `memory/store.py` — `get_profile`/`profile_note` now take an injected `repo: ClosetRepository` param instead of opening `SessionLocal()` + calling `crud.get_derivation_inputs` (Research §1). Deliberately NOT threaded through `GraphState` — a `ClosetRepository` object in LangGraph checkpointed state risks breaking `PostgresSaver` serialization; wiring happens via closure when `pipeline/graph.py` builds its nodes (Phase 7). `get_checkpointer()`'s raw psycopg pool left as-is (LangGraph's own storage backend, not `SessionLocal`/ORM), but now reads `core.config.get_settings()` instead of raw `os.environ` (added `database_url_direct`, `wtw_checkpointer_pool_max` to `Settings`) — consolidating into the one config layer per Research §10. Fixed two real mypy gaps while typing this: `connect_timeout` needed `int()` (psycopg stub is stricter than the float the legacy code passed), and `ConnectionPool`'s generic needed an explicit `Connection[dict[str, object]]` param to match its actual `row_factory=dict_row` runtime behavior. + test with a fake `ClosetRepository` (new — never had one)

**Checkpoint**: verified — no `from ..db import` or `from .. import crud` anywhere in `memory/` (grepped). `whattowear.memory.preferences`/`.store` import with zero env vars (24/24 import-safety cases pass). 22 memory tests pass, `ruff`/`ruff format` clean, `mypy src` clean except the two still-expected Phase 6/11 gaps (`whattowear.kb`, `whattowear.external.trends`).

## Phase 6: `external/` package (US1)

**Goal**: weather lookup (no key) and trend search + distillation, prompt extracted.
**Independent test**: `weather.py` unit tests against a stubbed HTTP client; `trends.py` unit test against a recorded Tavily fixture, no live call.

- [x] T025 [P] Port `external/weather.py` (Open-Meteo geocode + forecast, unchanged logic; fixed a real mypy gap — geocode `params` dict had mixed int/str values, requests' stub wants a narrower type, fixed by passing `"1"` not `1`, zero behavior change since requests URL-encodes both identically) + test (new — never had one)
- [x] T026 Port `external/trends.py` — extracted `_DISTILL_PROMPT` to `prompts/trends_distill.md` (`load_prompt("trends_distill")`); `..config.get_chat_model` → `..adapters.llm_gateway.get_chat_model`; `refresh_trend_cards`'s `L3_CARDS_PATH` (was `REPO_ROOT / "data" / "kb" / ...`, a path inside the repo) now resolves from `core.config.get_settings().corpus_local_dir` at call time, not a module-level constant — constitution Principle X, and the legacy path scheme doesn't exist in this rebuild's corpus model anyway. Also fixed a real mypy gap: `.content` on a chat message is typed `str | list[str | dict]` (multimodal responses); added an explicit `isinstance` guard that degrades to the same "malformed response" `None` return the code already had, rather than crashing on the untyped case. + test against mocked Tavily/gateway responses, no live call (new — never had one)

**Checkpoint**: verified — no inline prompt string remains in `trends.py` (grepped). `whattowear.external.weather`/`.trends` import with zero env vars (26/26 import-safety cases pass). 34 external tests pass; `retrieval/test_hybrid.py`'s 4 previously-skipped `TestRetrieveL3Live` cases now run and pass (20/20 in `tests/unit/retrieval/`, no skips). `ruff`/`ruff format` clean. `mypy src` clean except the one remaining expected gap (`whattowear.kb`, Phase 11).

## Phase 7: `pipeline/` package (US1, US2, US4) — DB coupling fix #1 and #3 of 3, docstring fix

**Goal**: the full LangGraph styling pipeline, both grounded and engine paths, zero direct DB/eval imports.
**Independent test**: `build_graph()`/`compile_graph()` succeed with an injected `ClosetRepository` + stub `LLMClient`/`VectorStore`; no live LLM call in the test.

- [ ] T027 Port `pipeline/context_assembler.py` — replace `load_wardrobe`'s `from ..db import SessionLocal` + `crud.list_wardrobe_items` with an injected `ClosetRepository.list_wardrobe_items` (Research §1) + test
- [ ] T028 [P] Port `pipeline/query_builder.py` + test
- [ ] T029 [P] Port `pipeline/validity.py` + test
- [ ] T030 [P] Port `pipeline/grounding.py` + test
- [ ] T031 [P] Port `pipeline/cite.py` + test
- [x] T032 ~~Port `pipeline/cache.py`~~ — **descoped**: `cache.py` imports `redis` directly (per-user suggestion cache, Feature 005). Brief Trap 5 explicitly excludes Redis/the suggestion cache from this slice ("belong to a later slice. Do not drag them in"), overriding the inventory's "keep" suggestion for this one module. Confirmed safe to defer: `graph.py` never imports `cache.py` — it's wired at the API layer (out of scope, feature 003+), not the pipeline itself. Not ported; left in `../app-legacy` for whichever feature adds caching back.
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
