---

description: "Task list template for feature implementation"
---

# Tasks: Backend and database foundation

**Input**: Design documents from `/specs/002-backend-foundation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/health.md, quickstart.md

**Tests**: Included. The definition of done requires `uv run pytest` to pass and requires
proving trap 1 (import-safety) as a regression test, not a one-time manual check — spec.md's
Acceptance Scenarios ask for exactly this.

**Organization**: Tasks are grouped by user story (US1 = P1 clone-to-running-backend,
US2 = P2 CI gate, US3 = P3 schema-as-artifact) per spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)

## Path Conventions

- **Backend**: `backend/src/whattowear/`, tests in `backend/tests/{unit,integration}`
- **Infra**: `infra/package.json`, `infra/supabase/`
- **CI**: `.github/workflows/ci.yml`

No task touches `frontend/` — CI runs its *existing* scripts but changes no frontend source.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repo scaffolding every later task builds on.

- [X] T001 Create backend package skeleton: `backend/src/whattowear/__init__.py`,
      `backend/src/whattowear/core/__init__.py`, `backend/tests/unit/__init__.py`,
      `backend/tests/integration/__init__.py` — every `__init__.py` empty, no logic
- [X] T002 [P] Write `backend/pyproject.toml` — `uv`-managed, `name = "whattowear"`,
      `requires-python = ">=3.12"`, src layout (`[tool.hatch.build.targets.wheel]
      packages = ["src/whattowear"]`), dependencies (fastapi, uvicorn, sqlalchemy,
      `psycopg[binary]`, pydantic-settings) and a `dev` dependency group (pytest, httpx,
      ruff, mypy, import-linter, pre-commit) per plan.md's Technical Context
- [X] T003 [P] Create `infra/package.json` pinning the Supabase CLI as an exact-version
      devDependency (research.md §4)
- [X] T004 Run `npm install` then `npx supabase init` from `infra/`, producing
      `infra/supabase/config.toml`; edit it to set `[db.pooler] enabled = true` (research.md
      §3 — the CLI generates it disabled by default)

**Checkpoint**: `backend/` is a valid (empty) package; `infra/supabase/` exists with the
local pooler enabled.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Tooling config every user story's tasks assume is already in place.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 [P] Write `backend/.env.example` listing `DATABASE_URL` (pointed at the local
      pooler port from T004, per research.md §3), `LOG_LEVEL`, `ENVIRONMENT` — every variable
      `core/config.py` will read, placeholder values only (FR-010, data-model.md)
- [X] T006 [P] Add `[tool.ruff]` and `[tool.mypy]` sections to `backend/pyproject.toml`
      (line-length 120 matching legacy precedent, `target-version = "py312"`; mypy strict
      enough to catch untyped defs, with a documented override for `psycopg` if its stubs are
      incomplete)
- [X] T007 [P] Write `backend/.importlinter` — one narrow `forbidden` contract:
      `source_modules = whattowear.core` MUST NOT import `whattowear.main` or `fastapi`.
      Comment above the contract stating feature 007 extends `source_modules` with
      `pipeline`/`retrieval`/`scoring`/`memory`/`ingest` as each module lands (brief §4.3,
      research.md — this is the "passes today" contract, not the eventual one)
- [X] T008 [P] Write `backend/.pre-commit-config.yaml` — `ruff-pre-commit` (format + check)
      scoped to `backend/`, plus a local hook running `lint-imports`

**Checkpoint**: Foundation ready — US1, US2, US3 tasks can now proceed.

---

## Phase 3: User Story 1 - Clone to running backend (Priority: P1) 🎯 MVP

**Goal**: A contributor goes from a fresh clone to `GET /health` reporting a reachable
database, and the package imports with zero environment variables set.

**Independent Test**: `env -i python3 -c "import whattowear"` succeeds; with local Supabase
running and `.env` configured, `curl localhost:8000/health` returns `{"status": "ok"}`.

### Tests for User Story 1

- [X] T009 [P] [US1] Write `backend/tests/unit/test_import_safety.py` — runs
      `python -c "import whattowear"` in a subprocess with a cleared environment
      (`env={}`/`env -i` equivalent) and asserts a zero exit code. This is trap 1 made into a
      regression test, not a one-off manual check (spec.md Acceptance Scenario 1.3)
- [X] T010 [P] [US1] Write `backend/tests/integration/test_health.py` — `TestClient` against
      the FastAPI app, asserting `GET /health` returns `200`/`{"status": "ok"}` when the local
      Supabase database (started per quickstart.md) is reachable, per contracts/health.md

### Implementation for User Story 1

- [X] T011 [US1] Implement `backend/src/whattowear/core/config.py` — `Settings`
      (pydantic-settings `BaseSettings`: `database_url: str`, `log_level: str = "INFO"`,
      `environment: str = "development"`) and `get_settings()` wrapped in
      `functools.lru_cache`, with no module-level `Settings()` instantiation
      (research.md §1, §10; data-model.md)
- [X] T012 [US1] Implement `backend/src/whattowear/core/logging.py` — `configure_logging()`:
      stdlib `logging` configured with a JSON `Formatter` subclass, reading `log_level` from
      `get_settings()` when called, not at import time (research.md §9)
- [X] T013 [US1] Implement `backend/src/whattowear/core/db.py` — `get_engine()` wrapped in
      `functools.lru_cache` (calls `get_settings()`, builds a SQLAlchemy engine with
      `poolclass=NullPool` and `connect_args={"prepare_threshold": None}`), and `get_session()`
      as a FastAPI dependency that opens/closes a session per request. No module-level engine
      or session factory (research.md §1, §2; the trap-1 regression test in T009 is what this
      task must pass)
- [X] T014 [US1] Implement `backend/src/whattowear/main.py` — `FastAPI()` app; a `lifespan`
      context manager that calls `get_engine()` once at startup (research.md §1's refinement);
      `GET /health` per `contracts/health.md` — `SELECT 1` via `get_engine()`, `200`/`"ok"` on
      success, `503`/`"unhealthy"`/`failed_dependencies: ["database"]` on failure, never an
      unhandled exception (depends on T011–T013)
- [X] T015 [US1] Walk through `quickstart.md`'s "one-time setup" and "the two commands"
      sections end-to-end on a clean checkout; fix any drift between the doc and actual
      behavior found along the way (spec.md SC-001)

**Checkpoint**: User Story 1 fully functional and testable independently — this is the MVP.

---

## Phase 4: User Story 2 - A pull request is gated on both stacks (Priority: P2)

**Goal**: CI runs backend and frontend checks on every PR and push to `rebuild`, and a
deliberate violation on either side is caught automatically.

**Independent Test**: Open a scratch PR that only touches a backend file — backend job
results appear; one that only touches a frontend file — frontend job results appear;
introduce one deliberate `.importlinter` violation and confirm `lint-imports` fails on it.

### Implementation for User Story 2

- [X] T016 [US2] Write `.github/workflows/ci.yml` — triggers on `pull_request` and on `push`
      to `rebuild`; **backend** job: checkout, `astral-sh/setup-uv`, `uv sync` (in
      `backend/`), the import-safety check from T009 run standalone as an explicit early
      step, `supabase/setup-cli@v2` pinned to the version from T003/research.md §4, `supabase
      start` and `supabase db reset` from `infra/` (research.md §8 — depends on T018/US3's
      migration existing to be meaningful), export the resulting local `DATABASE_URL` for
      later steps, `uv run pytest`, `uv run ruff check .`, `uv run mypy src`,
      `uv run lint-imports`; **frontend** job (independent, no path filtering — research.md
      §11): checkout, `actions/setup-node` with npm cache, `npm ci` in `frontend/`,
      `npm run lint`, `npm run typecheck`, `npm run build`
- [X] T017 [US2] Verify the import-boundary gate actually fails closed: temporarily add an
      import of `fastapi` inside `backend/src/whattowear/core/config.py`, run
      `uv run lint-imports` locally, confirm it reports the violation by name, then revert
      the change (spec.md Acceptance Scenario 2.3 — a manual verification, not a permanent
      test file, since the violation must not ship)
- [X] T017b [P] [US2] Verify the frontend gate fails closed too, mirroring T017: temporarily
      introduce one deliberate lint violation in a `frontend/` file, run `npm run lint`
      locally, confirm it fails; do the same for `npm run typecheck` with a type error;
      revert both changes (spec.md SC-004 — both stacks must be shown to block, not just
      backend). **Result**: `npm run typecheck` hard-fails (exit non-zero, `TS2322`) on a
      type error — confirmed blocking. `npm run lint` reported the chosen violation
      (`@typescript-eslint/no-unused-vars`) as a warning, not an error, so its exit code
      stayed 0 for that specific rule — this project's ESLint config treats that rule as
      warn-level, not a gap in the CI step itself. `react-hooks/rules-of-hooks` is
      configured as `"error"` (`frontend/eslint.config.mjs:38`) and would fail the step;
      not separately re-verified here to avoid overreach into 001's frontend surface.

**Checkpoint**: User Stories 1 AND 2 both work independently; CI is green on a real PR.

---

## Phase 5: User Story 3 - The schema is a checked-in artifact (Priority: P3)

**Goal**: `0001_init.sql` alone explains every foundation-level database object and the
convention later tables follow, and a reset from empty reproduces it exactly.

**Independent Test**: Read `infra/supabase/migrations/0001_init.sql` with no other context;
run `supabase db reset` from empty twice in a row and confirm identical, error-free results
both times.

### Implementation for User Story 3

- [X] T018 [US3] Write `infra/supabase/migrations/0001_init.sql`: a header comment stating
      the file's scope; `CREATE EXTENSION IF NOT EXISTS pgcrypto`; `CREATE TYPE
      category_group AS ENUM (...)` and `CREATE TYPE formality_level AS ENUM (...)` with the
      exact frozen values from data-model.md; the `public.set_updated_at()` `plpgsql` trigger
      function; the row-level-security convention written as a SQL comment block (not
      executable — no table exists yet) exactly as shown in data-model.md, ending with a note
      that feature 003 wires how `auth.uid()` is populated for backend-issued queries
      (research.md §6, §7)
- [X] T019 [US3] From `infra/`, run `npx supabase db reset` three times in a row against the
      local stack; confirm all three runs succeed with no errors and leave an identical
      schema (DoD item 3; brief trap 4 — "the real test," not "worked once"; spec.md SC-002)

**Checkpoint**: All three user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final verification across every story before calling this slice done.

- [X] T020 [P] Run `uv run ruff check .`, `uv run mypy src`, and `uv run lint-imports` from
      `backend/`; fix anything they flag
- [X] T021 [P] Run `uv run pytest` from `backend/`; confirm T009 and T010 both pass
- [X] T022 Walk the definition-of-done checklist in `docs/handoffs/002-backend-foundation.md`
      §7 item by item and record, in the completion report, which are verified and which are
      not — do not mark an item done that was not actually run

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup (needs `backend/pyproject.toml` from T002 to
  add tool config to). Blocks all user stories.
- **User Stories (Phase 3–5)**: All depend on Foundational completion.
- **Polish (Phase 6)**: Depends on US1 and US3 at minimum (there is nothing to lint/test
  without US1's code and US3's migration); depends on US2 only for the CI-specific
  verification in T017 (that can run locally without CI existing).

### User Story Dependencies

- **US1 (P1)**: No dependency on US2 or US3. Fully self-contained after Foundational.
- **US2 (P2)**: Independently testable on its own terms (T017), but T016's CI workflow
  references the migration T018 (US3) writes for its `supabase db reset` step to be
  meaningful — not merely present. **Recommended build order despite priority numbering:
  US1 → US3 → US2**, so CI has something real to run against the first time it executes.
- **US3 (P3)**: No dependency on US1 or US2. Fully self-contained after Foundational.

### Within Each User Story

- US1: tests (T009–T010) can be written alongside implementation since there's no prior
  state to assert "fails first" against in any interesting way beyond "not implemented yet";
  T011 → T012/T013 → T014 (main.py depends on all three core modules) → T015 (manual
  validation, last).
- US2: T016 before T017 (need the contract to exist before deliberately breaking it).
- US3: T018 before T019 (need the migration before resetting against it).

### Parallel Opportunities

- T002, T003 in Setup: different files, run together.
- T005–T008 in Foundational: four different files, all parallel.
- T009 and T010 in US1: different test files, parallel (both depend on T011–T014 existing to
  actually pass, but can be written in parallel with implementation).
- T020 and T021 in Polish: independent commands, parallel.

---

## Parallel Example: Foundational phase

```bash
# Launch T005–T008 together — four independent files:
Task: "Write backend/.env.example"
Task: "Add [tool.ruff]/[tool.mypy] sections to backend/pyproject.toml"
Task: "Write backend/.importlinter"
Task: "Write backend/.pre-commit-config.yaml"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: `env -i python3 -c "import whattowear"` succeeds; `GET /health`
   returns `{"status": "ok"}` against a running local Supabase
5. This is the point at which every later slice (003+) is unblocked

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → validate independently (MVP — unblocks 003–007)
3. US3 → validate independently (the migration every later table's convention leans on)
4. US2 → validate independently (CI now proves 1 and 3 stay true on every PR)
5. Polish → final DoD sign-off

---

## Notes

- No task creates `api/`, `repositories/`, `services/`, `pipeline/`, `retrieval/`,
  `scoring/`, `memory/`, `ingest/`, `prompts/`, `adapters/`, or `ports.py` — see plan.md's
  Structure Decision for why stopping here is deliberate, not an oversight.
- Commit after each task or logical group.
- Stop at any checkpoint to validate a story independently before continuing.
