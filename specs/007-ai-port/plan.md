# Implementation Plan: AI layer port

**Branch**: `feat/007-ai-port` | **Date**: 2026-07-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-ai-port/spec.md`

## Summary

Port `../app-legacy/backend/src/whattowear/`'s AI layer (schema/colors/categories,
`scoring/`, `retrieval/`, `pipeline/`, `memory/`, `external/`, `ingest/`, `vision.py`,
`eval/`) into `backend/src/whattowear/`, preserving every behaviour the recorded eval
baselines measure, while fixing the two documented coupling defects (AI modules importing
the DB session factory directly; production importing the `eval` package) and extracting
the five inline prompts to versioned files. The technical approach is a `ports.py` Protocol
layer (`VectorStore`, `LLMClient`, `ClosetRepository`) that every AI module depends on
instead of a concrete database/vector-store/LLM SDK import, plus a fixture-backed
`ClosetRepository` implementation that lets the golden-set eval run without a real
Postgres closet schema (which does not exist in this rebuild yet — see Research §5).

## Technical Context

**Language/Version**: Python 3.12 (matches `backend/pyproject.toml`)

**Primary Dependencies**: LangGraph (`StateGraph`, checkpointers), LangChain core +
`langchain-litellm` (chat) + `langchain-openai` (embeddings) + `langchain-cohere` (rerank)
+ `langchain-qdrant`, `qdrant-client`, `langsmith` (mandatory tracing), Tavily client
(trend search), Pydantic v2 (`schema.py`'s contracts), PyYAML (manifest/golden-set),
`psycopg[binary]` + a connection pool (LangGraph's `PostgresSaver`)

**Storage**: Qdrant (vector index, local Docker container — `infra/docker-compose.yml`);
Postgres via the existing `core.db` lazy engine, reached only through `ports.py`'s
`ClosetRepository` Protocol, never a direct session import. No new tables land in this
feature — closet/catalog persistence is a separate feature's schema.

**Testing**: `pytest` (unit, one new test per ported module per the handoff); the existing
`src/whattowear/eval/` harness (golden-set runner, live-LLM, not part of `pytest`/CI); the
isolated `backend/evals/` project (RAGAS + openevals scoring of the harness's JSONL output)

**Target Platform**: Linux server (Railway), local Docker for dev

**Project Type**: Backend library slice inside the existing `backend/` service — no new
top-level project

**Performance Goals**: Not a target of this feature; behaviour parity is the target, not
speed. No new latency budget is introduced.

**Constraints**: Zero live LLM/embedding/rerank/web-search calls in CI (constitution Quality
Bar) — all `pytest` coverage runs against recorded fixtures or pure-Python paths, never the
real gateway. AI modules must import with zero environment variables set.

**Scale/Scope**: 53 legacy files / 6,044 lines surveyed (inventory §"Scope surveyed"); ~40
land in this port (web/persistence-layer files `api.py`, `auth.py`, `db.py`, `crud.py`,
`models.py`, `storage.py` are explicitly out of scope — feature 003's territory). 24-case
golden set, 40-item fixture wardrobe, 16-file/47 MB external corpus (never committed).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **I — Salvaged AI code is authoritative.** This plan refactors, never regenerates:
      every scorer, retriever, chunker and the graph topology are lifted with understanding,
      not rewritten to taste. Every refactor (DI fixes, prompt extraction, docstring
      correction) is covered by the eval-run task in Phase 3 (tasks.md) before any other
      improvement lands, per the handoff's order of work.
- [x] **II — Deterministic scoring.** All four dimension scorers + `combine.rank_outfits`
      port unchanged, pure Python, no LLM call, unit-tested. `verify_grounding` (deterministic
      guard) stays the last checkpoint before `explain` builds the response on every path.
      `graph.py`'s stale "the LLm never ranks" docstring is corrected to match the
      constitution's actual v2.0.0 wording (Research §3) — not carried forward.
- [x] **III — Style gates wardrobe.** `style_retrieval → build_query → wardrobe_retrieval`
      edge order ports unchanged from `build_graph()`; never parallelized.
- [x] **IV — Grounded output.** `pipeline/grounding.py`'s `verify_outfit_grounding` and
      `pipeline/cite.py`'s citation checks port unchanged; the empty-citation-on-honest-
      fallback behaviour is preserved exactly (Research §4, harness blind-spot note).
- [x] **V — Scorers are eval metrics.** `eval/properties.py`'s predicates move to
      `scoring/properties.py` (Research §2) so the eval harness imports the domain instead of
      the reverse — same functions, same behaviour, corrected direction.
- [x] **VI — Schema stability.** `schema.py` ports the frozen taxonomy unchanged; no new
      formality scale, no renamed category group.
- [ ] **VII — Contracts.** N/A — this feature has no API surface (no FastAPI routes land
      here; feature 003 owns `api/v1/routes/`). Nothing to generate OpenAPI types from yet.
- [ ] **VIII — Visual truth.** N/A — backend-only, no UI.
- [ ] **IX — One codebase.** N/A — backend-only, no frontend routes touched.
- [x] **X — Documents are data.** `infra/corpus.yaml` describes every ingested source;
      ingestion is a CLI (`ingest.cli`), idempotent by content hash, reading only from
      `CORPUS_LOCAL_DIR` (env var, never a literal path); nothing under `../w2w-corpus/` is
      committed. The one tracked exception (`evals/fixtures/`) matches the constitution's own
      carve-out.

No unresolved violations. Three principles (VII, VIII, IX) are N/A because this slice has no
API/UI surface — recorded as N/A, not skipped silently.

## Project Structure

### Documentation (this feature)

```text
specs/007-ai-port/
├── plan.md              # this file
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/             # Phase 1 output — ports.py Protocol surface, prompt front-matter
│   ├── ports.md
│   └── prompt-front-matter.md
└── tasks.md               # Phase 2 output (/speckit-tasks — not this command)
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml                    # + langgraph, langchain*, qdrant-client, tavily, pyyaml, psycopg-pool
├── src/whattowear/
│   ├── ports.py                      # NEW — VectorStore, LLMClient, ClosetRepository Protocols
│   ├── schema.py                     # ported — frozen taxonomy + contracts
│   ├── colors.py                     # ported — hex source of truth, name derivation
│   ├── categories.py                 # ported — taxonomy grouping
│   ├── kb.py                         # ported — process-wide KB singleton, uses ports.VectorStore
│   ├── vision.py                     # ported — prompt extracted to prompts/vision_system.md
│   ├── core/
│   │   └── config.py                 # EXTENDED — AI gateway / Qdrant / Cohere / Tavily settings
│   ├── adapters/
│   │   └── closet_fixture.py         # NEW — fixture-backed ClosetRepository (Research §5)
│   ├── prompts/                      # NEW — the 5 extracted prompts, versioned front-matter
│   │   ├── generator_system.md
│   │   ├── vision_system.md
│   │   ├── engine_system.md
│   │   ├── trends_distill.md
│   │   └── judge.md
│   ├── scoring/
│   │   ├── properties.py             # NEW home for eval/properties.py's predicates
│   │   ├── color_harmony.py  combine.py  formality_coherence.py
│   │   ├── silhouette_balance.py  weather_fitness.py  __init__.py
│   ├── retrieval/
│   │   ├── base.py  baseline.py  hybrid.py  advanced.py
│   ├── memory/
│   │   ├── store.py                  # DI-fixed: ClosetRepository, not SessionLocal
│   │   └── preferences.py
│   ├── external/
│   │   ├── weather.py
│   │   └── trends.py                 # prompt extracted to prompts/trends_distill.md
│   ├── pipeline/
│   │   ├── graph.py                  # DI-fixed; docstring corrected; imports scoring.properties
│   │   ├── engine.py                 # prompt extracted to prompts/engine_system.md
│   │   ├── generator.py              # prompt extracted to prompts/generator_system.md
│   │   ├── context_assembler.py  query_builder.py  cite.py  validity.py  grounding.py
│   │   # cache.py NOT ported — needs Redis directly; brief Trap 5 defers Redis/the
│   │   # suggestion cache to a later slice. graph.py never imports it.
│   ├── ingest/
│   │   ├── build_kb.py  chunkers.py  loaders.py  wiki_refine.py
│   │   └── cli.py                    # NEW — the ingestion CLI entry point (FR-011)
│   └── eval/
│       ├── harness.py  golden_set.py  judge.py  properties.py  test_users.py  vision_harness.py
│       # properties.py becomes a thin re-export of scoring.properties (V)
├── tests/
│   ├── unit/                         # + one test per ported module
│   └── evals/                        # fixture-backed graph-level tests, no live calls
└── evals/                            # the SECOND, isolated uv project (RAGAS/openevals) —
    ├── pyproject.toml                # pins langchain-community==0.3.31 — AND, co-located in
    ├── common.py  judge.py  score_ragas.py   # the same directory, not part of that project:
    ├── fixtures/wardrobe.json        # tracked exception (constitution X) — the 40-item fixture
    └── golden_set.yaml               # tracked — the 24-case golden set

infra/
├── corpus.yaml                       # NEW — the tracked corpus manifest
├── docker-compose.yml                # DONE — pinned qdrant/qdrant:v1.15.5
└── supabase/migrations/              # untouched — no schema change in this feature
```

**Structure Decision**: Everything above lives inside the existing `backend/` package —
no new top-level directory. `adapters/` is new (one file: the fixture `ClosetRepository`).
`prompts/` is new (five files). `backend/evals/` is one directory serving two purposes that
don't conflict: it is the isolated RAGAS/openevals `uv` project (`pyproject.toml`,
`common.py`, `judge.py`, `score_ragas.py`, `package = false` — no Python package installed
from it, just scripts), and it also holds the two tracked data files the constitution's
"evals/fixtures/" carve-out and the handoff's Trap 7 refer to (`fixtures/wardrobe.json`,
`golden_set.yaml`) — plain data, not part of that isolated project's dependency tree, so
co-locating them causes no conflict. `web/persistence` files (`api.py`, `auth.py`, `db.py`,
`crud.py`, `models.py`, `storage.py`) are explicitly not touched by this feature.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|---------------------------------------|
| Two isolated `uv` projects for evals (`src/whattowear/eval/` deps in the main project, `backend/evals/` as a second `pyproject.toml`) | `backend/evals/`'s RAGAS fork pins `langchain-community==0.3.31`; `retrieval/advanced.py` needs `langchain-cohere>=0.4`. The two version ranges do not overlap in one lockfile. | A single project was tried implicitly by the prototype's own history (inventory §Q4) and rejected — this is a real, structural dependency conflict, not accidental duplication. Merging them would force downgrading `langchain-cohere`, silently changing rerank behaviour (a behaviour change with no eval covering it). |
| `adapters/closet_fixture.py` — a fixture-backed `ClosetRepository`, not the eventual Postgres-backed one | The rebuild's schema (`infra/supabase/migrations/0001_init.sql`) has no wardrobe/catalog tables yet — that lands with closet persistence, a different feature. Without *some* concrete `ClosetRepository`, neither the eval harness nor a unit test can exercise `graph.py`'s `verify_grounding` node or `context_assembler.load_wardrobe`. | Waiting for the real schema would block this feature's entire eval gate on a feature it doesn't own. A fixture adapter satisfies `ports.py`'s contract today and is a pure swap-out later — no pipeline code changes when the real adapter lands, only the wiring that constructs it. |
