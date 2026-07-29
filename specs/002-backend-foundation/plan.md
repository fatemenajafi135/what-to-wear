# Implementation Plan: Backend and database foundation

**Branch**: `002-backend-foundation` | **Date**: 2026-07-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-backend-foundation/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Stand up the importable `whattowear` Python package, a local Supabase stack, one
hand-written foundation migration, and CI gating both stacks — with no product endpoint, no
salvaged AI code, and no `ports.py`. The one constraint that shapes every technical choice
below: the package must import cleanly with zero environment variables set, which means
config and database-engine construction are lazy and injected rather than eager and
module-level (the legacy `db.py` defect this slice exists to not reproduce). See
`research.md` for the judgment calls this required.

## Technical Context

**Language/Version**: Python 3.12, fixed by the constitution's Technology Constraints.

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, `psycopg[binary]` (psycopg3),
`pydantic-settings`, Uvicorn. Dev-only: pytest, httpx (FastAPI `TestClient`), ruff, mypy,
`import-linter`, `pre-commit`.

**Storage**: PostgreSQL via local Supabase (Postgres + Auth + Storage in Docker), reached
through the Supabase transaction pooler even locally (research.md §2–3). No product data —
this slice's own migration defines foundation objects only (research.md §6–7).

**Testing**: pytest, against a real local Supabase instance in both dev and CI
(research.md §8) — no mocked database layer.

**Target Platform**: Linux server (Railway, per constitution), developed and CI'd on Linux
containers (`ubuntu-latest`).

**Project Type**: Web service backend (one slice of the fixed `frontend/` + `backend/` +
`infra/` layout — no project-type choice to make).

**Performance Goals**: N/A. This slice has one route (`GET /health`) with no product traffic
shape to target yet; success is measured by the developer-facing outcomes in Success
Criteria (setup time, reproducibility), not request throughput.

**Constraints**: `python -c "import whattowear"` MUST succeed with zero environment
variables set (FR-001, the hard constraint this whole plan is organized around). Local
Supabase only — no cloud project (FR-004). No secrets committed (FR-010).

**Scale/Scope**: One FastAPI route, one migration file, one CI workflow, five backend source
files (`__init__.py` ×2, `core/config.py`, `core/logging.py`, `core/db.py`, `main.py`) plus
their tests. Deliberately small — see Project Structure's Structure Decision for the exact
file list and why it stops there.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Answer each gate explicitly. Mark N/A where a principle genuinely does not apply to this
feature, and say why in one line. Any gate that cannot be satisfied goes into Complexity
Tracking with a justification, or the plan does not proceed to `/speckit-tasks`.

- [x] **I — Salvaged AI code is authoritative.** N/A. This slice touches no AI module —
      no retrieval, chunking, ingest, KB, scoring, pipeline, or eval-harness code exists in
      this diff at all (brief §5: "no salvaged AI code"). Nothing to regenerate or refactor.
- [x] **II — Deterministic scoring.** N/A. No outfit scoring of any kind exists in this
      slice — there are no outfits, no items, and no scorers. The principle has no surface
      to apply to yet.
- [x] **III — Style gates wardrobe.** N/A. No retrieval of any kind (style or wardrobe)
      exists in this slice.
- [x] **IV — Grounded output.** N/A. No suggestion, rationale, or citation exists in this
      slice — the only response body this slice produces is `GET /health`'s status dict.
- [x] **V — Scorers are eval metrics.** N/A. No quality judgment of any kind (scorer or
      prompt) exists in this slice.
- [x] **VI — Schema stability.** Applies, and is satisfied. `0001_init.sql` encodes the
      frozen taxonomy's two enums (`category_group`'s six values, `formality_level`'s six
      values) verbatim from the constitution — no parallel scale, no renamed group. See
      data-model.md.
- [x] **VII — Contracts.** Partially applies. No frontend consumption exists yet (that's a
      later slice), but this slice's own contract discipline matters for what comes after:
      `GET /health`'s response shape is defined once, in `contracts/health.md`, generated
      from the same FastAPI/Pydantic route that serves it — not hand-duplicated anywhere.
      Full OpenAPI-generated frontend types become relevant once a frontend consumes a
      backend route, starting at feature 004.
- [x] **VIII — Visual truth.** N/A. This slice has no screen, no UI, and touches nothing
      under `frontend/`.
- [x] **IX — One codebase.** N/A. No route, screen, or chrome exists in this slice; nothing
      to diverge between form factors.
- [x] **X — Documents are data.** N/A. This slice introduces no document, corpus entry, or
      ingestion path of any kind — `infra/corpus.yaml` is untouched.

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

<!--
  The repository layout is FIXED by the constitution ("Technology Constraints":
  frontend/, backend/, infra/, design/, docs/ — do not restructure). There is no
  layout choice to make. List only the concrete paths this feature touches.

  There is deliberately no mobile-app option. Principle IX: one Next.js codebase
  serves the desktop web experience and the installed mobile PWA. Creating ios/,
  android/, or any second frontend is a constitutional violation, not an option.
-->

```text
frontend/                     # Next.js App Router + TypeScript. Web AND installed PWA.
├── app/                      # routes — identical at every form factor
├── components/
├── styles/                   # token layers: system → semantic → theme blocks
└── public/                   # icons/ and logo.svg already exist; do not regenerate

backend/
├── pyproject.toml
├── src/whattowear/           # src layout, single package
│   ├── main.py  api/v1/routes/  core/  schemas/  models/
│   ├── repositories/         # ALL database access
│   ├── services/             # use cases: repositories + AI
│   ├── pipeline/ retrieval/ scoring/ memory/ ingest/   # framework-free
│   ├── prompts/              # prompt FILES, loaded by name — never inline strings
│   ├── adapters/  ports.py   # Protocols; AI reaches the DB only through these
│   └── evals/
└── tests/{unit,integration,evals}

infra/
├── corpus.yaml               # the tracked corpus manifest
└── supabase/migrations/      # the ONLY migration system — Alembic is not used
```

**Structure Decision**: This slice creates, and stops at, exactly this much of the eventual
layout shown above — no `api/`, `repositories/`, `services/`, `pipeline/`, `retrieval/`,
`scoring/`, `memory/`, `ingest/`, `prompts/`, `adapters/`, or `ports.py` directory/file is
created now, even empty. Those belong to the features that give them a real caller (004+ for
the data-access layer, 007 for the AI layer); an empty directory with an `__init__.py` and no
caller is the speculative abstraction the Quality Bar prohibits, just in directory form
instead of code form.

```text
backend/
├── pyproject.toml            # uv-managed, Python 3.12, src layout
├── .env.example               # every var core/config.py reads
├── .importlinter               # narrow AI-independence contract, extended per-module in 007
├── .pre-commit-config.yaml
├── src/whattowear/
│   ├── __init__.py             # package root — MUST import with zero env vars set
│   ├── main.py                 # FastAPI app, lifespan startup, GET /health
│   └── core/
│       ├── __init__.py
│       ├── config.py           # get_settings() — lazy, lru_cache'd, no module-level instantiation
│       ├── logging.py          # configure_logging() — stdlib logging, JSON formatter
│       └── db.py               # get_engine()/get_session() — lazy, NullPool, prepare_threshold=None
└── tests/
    ├── unit/
    │   └── test_import_safety.py   # subprocess: `import whattowear` with env -i
    └── integration/
        └── test_health.py          # TestClient against a real local Supabase DB

infra/
├── package.json                # pins the Supabase CLI devDependency (research.md §4)
└── supabase/
    ├── config.toml              # from `supabase init`; local pooler enabled (research.md §3)
    └── migrations/
        └── 0001_init.sql        # extensions, both frozen-taxonomy enums, updated_at trigger,
                                  # RLS convention as written comments — no product table

.github/workflows/ci.yml         # backend + frontend jobs, both unconditional (research.md §11)
```

`frontend/` is untouched by this slice (brief §5: "no frontend change") — CI adds a job that
runs the frontend's *existing* `lint`/`typecheck`/`build` scripts, but no frontend source
changes.

## Complexity Tracking

No constitution violations in this plan — every gate above is either satisfied directly
(VI, and VII partially) or is a genuine N/A because this slice has no surface for that
principle to apply to (I–V, VIII–X). Nothing in this table.
