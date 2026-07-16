# Implementation Plan: Production Hardening

**Branch**: `005-production-hardening` | **Date**: 2026-07-16 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-production-hardening/spec.md`

## Summary

Four independent hardening slices, none of which change what an outfit
suggestion contains or how it's chosen (FR-011): (1) finish the three
Feature-003 deploy steps that were never completed (Supabase Storage
bucket + RLS, Railway backend + Redis addon, Vercel frontend) so the app is
actually publicly reachable; (2) a deterministic post-generation
"grounding" filter — a new `pipeline/grounding.py` + a new `verify_grounding`
graph node between `score_and_rank` and `explain` — that drops any outfit
referencing an item id not in the requester's own wardrobe, as a safety net
on top of the existing constitution-mandated deterministic selection;
(3) an explicit, per-user Redis cache around the whole `/suggest` graph
invocation, keyed by the requester's id plus normalized context plus a hash
of their current wardrobe state, so a repeated equivalent request skips
retrieval and generation entirely (not merely LiteLLM's own per-call
semantic cache, which can't reach retrieval and risks fuzzy false-positive
matches — see research.md §2 for why); (4) swap `config.py`'s LangChain
model factories from `langchain_openai` classes to `langchain-litellm`'s
`ChatLiteLLM`, still pointed at the existing Vercel AI Gateway, so every
chat-completion call site gets automatic retry-on-transient-failure and
LangSmith-visible cost/usage for free, with zero change to any of the four
call sites that consume it.

## Technical Context

**Language/Version**: Python 3.12 (backend, unchanged). No frontend code
changes this feature (deploy config only).

**Primary Dependencies**: New — `litellm`, `langchain-litellm` (LLM routing,
§1), `redis` (cache, §2). Existing, unchanged — FastAPI, SQLAlchemy,
LangGraph, `langchain-openai` (kept for embeddings only, see research.md §1).

**Storage**: No new Postgres tables (data-model.md — this feature adds none).
Redis (already the locked stack's cache backend) holds cache entries only,
non-durable by design (TTL + fingerprint-keyed, never the source of truth).

**Testing**: pytest, matching the existing suite's structure — new unit
tests for `pipeline/grounding.py` (pure function) and the cache
key-derivation function (pure function), a new integration test exercising
the `verify_grounding` node via the compiled graph, and a cache
hit/miss/invalidation-on-edit integration test against a real (test) Redis
instance. Eval no-regression gate (`eval/harness.py`) re-run before merge —
this feature touches the LLM call path (§1) and adds a filtering step after
`score_and_rank` (§3), both within Principle I's scope.

**Target Platform**: Linux server on Railway (backend, + its Redis addon),
Vercel (frontend, unchanged) — the deploy targets already locked; this
feature is what finally makes them live (US1).

**Project Type**: Web application (existing `backend/` + `frontend/` split,
unchanged). All four slices are backend-only except the deploy steps.

**Performance Goals**: SC-003 — a cache hit responds in well under a second
(no retrieval/generation/LLM round trip in the path), versus the existing
multi-second full-pipeline latency for a miss (unchanged by this feature).

**Constraints**: FR-011 — no change to outfit contents or selection logic.
Cache reuse strictly per-user (this session's clarification) — the
requester's verified JWT `sub` is part of the cache key by construction, so
cross-user reuse cannot happen structurally, not just by policy. Grounding
check must run for both the live `/suggest` endpoint and `eval/harness.py`'s
direct graph invocation (Principle I: no forked pipeline path) — satisfied
by putting it in the graph itself, not in `api.py`.

**Scale/Scope**: 1 new module (`pipeline/grounding.py`), 1 new graph node
+ edge change, 1 new module (`pipeline/cache.py`), `api.py`'s
`suggest_endpoint` gains a cache check/write and `/health` gains real
dependency checks (FR-012, a `/speckit.analyze` finding — see research.md
§3a), `config.py`'s three factory functions get new internals (signatures
unchanged), 2 new dependencies + 1 new env var, 3 manual deploy steps
(owner-only, status TBD — see below).

**Manual/owner-only prerequisite**: the Supabase Storage bucket, Railway
project (+ Redis addon), and Vercel project from Feature 003 may or may not
already exist — this session doesn't have dashboard access to check on its
own and confirms status with the user before attempting any live-deploy
task. This does not block the code-only work (§2-4 above and their tests),
which has no dependency on live infrastructure.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Existing Pipeline Is Authoritative** — PASS. `pipeline/graph.py`'s
  eight existing nodes and their order are unchanged; one node
  (`verify_grounding`) is added between two existing nodes, not a rewrite.
  `eval/harness.py` invokes the same compiled graph, so it exercises the new
  node identically to the live endpoint — no forked path. Eval no-regression
  gate re-run before merge (quickstart.md).
- **II. Deterministic Core, LLM At The Edges** — PASS. The grounding check
  is a pure Python predicate (`item_id in wardrobe_by_id`), not an LLM call.
  The cache key derivation is pure (hash of normalized fields), not an LLM
  call. Neither touches what the LLM does (write rationale text, in
  `generator.py`, untouched).
- **III. Style Knowledge Gates Wardrobe Retrieval** — N/A. No change to
  retrieval ordering; `style_retrieval` still gates `wardrobe_retrieval`
  unchanged. (On a cache hit, neither runs at all — that's the point, not a
  reordering of them when they do run.)
- **IV. Grounded Output Only** — PASS, and this feature is precisely an
  additional, explicit enforcement of this principle (US2) — a safety net
  on top of, not instead of, the existing guarantee (per spec.md's
  Assumptions).
- **V. Scoring Functions Are Eval Metrics** — N/A. No new outfit-quality
  scoring dimension is added; `verify_grounding` is a correctness filter,
  not a quality score, so it has no eval-metric counterpart to reuse.
- **VI. Schema Stability** — PASS. No taxonomy change. The cache value is a
  `SuggestResult.model_dump()` — the existing response shape, verbatim.
- **VII. Single Source Of Truth For Contracts** — PASS. `/suggest`'s
  request/response Pydantic shapes are unchanged (contracts/suggest.md
  addendum); no frontend type regeneration needed since nothing in the
  OpenAPI schema changes.

No violations. Complexity Tracking table not needed.

**Post-Phase-1 re-check**: unchanged — the two config.py factory functions
and the two new small modules (`grounding.py`, `cache.py`) are the entire
surface; no repository pattern, service layer, or ABC was introduced for
either the cache or the LLM routing (each has exactly one concrete backend
— Redis, LiteLLM/the gateway — so a swappable-interface layer would violate
the simplicity clause, not satisfy it).

## Project Structure

### Documentation (this feature)

```text
specs/005-production-hardening/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   └── suggest.md        # Phase 1 output — addendum to 002's contract
└── tasks.md               # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── src/whattowear/
│   ├── config.py                 # get_chat_model/get_judge_model -> ChatLiteLLM internals;
│   │                              #   get_embeddings unchanged (research.md §1)
│   ├── pipeline/
│   │   ├── graph.py               # + verify_grounding node, wired between
│   │   │                          #   score_and_rank and explain
│   │   ├── grounding.py           # NEW: verify_outfit_grounding() pure function
│   │   └── cache.py               # NEW: cache key derivation + Redis get/set,
│   │                              #   used by api.py, not a graph node (it wraps
│   │                              #   whether the graph runs at all)
│   └── api.py                     # suggest_endpoint: cache check before graph.invoke,
│                                  #   cache write after a fresh result
├── pyproject.toml                 # + litellm, langchain-litellm, redis
├── .env.example                   # + REDIS_URL
└── tests/
    ├── unit/
    │   ├── pipeline/
    │   │   └── test_grounding.py   # NEW: verify_outfit_grounding() cases
    │   │                           #   (tests/unit/pipeline/ already exists
    │   │                           #   for pipeline/graph.py's own tests)
    │   └── test_cache.py           # NEW: cache key derivation (pure part)
    └── integration/
        ├── test_grounding_graph.py # NEW: bad item id dropped via compiled graph
        └── test_suggest_cache.py   # NEW: hit/miss/invalidation-on-edit against test Redis

(no frontend changes — deploy config only, tracked in tasks.md, not new code)
```

**Structure Decision**: Existing `backend/` + `frontend/` split, unchanged.
No new top-level directory. `pipeline/grounding.py` and `pipeline/cache.py`
are the only new modules, both flat additions to the existing `pipeline/`
package alongside `cite.py`/`query_builder.py`/`context_assembler.py` —
same pattern as every prior feature's new deterministic-logic modules
(`scoring/` in 002, `memory/preferences.py` in 004).

## Complexity Tracking

*No constitution violations — table not applicable.*
