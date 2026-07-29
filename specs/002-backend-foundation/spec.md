# Feature Specification: Backend and database foundation

**Feature Branch**: `002-backend-foundation`

**Created**: 2026-07-29

**Status**: Draft

**Input**: User description: "Backend and database foundation. Stand up the Python package
(backend/src/whattowear/ per constitution layout), local Supabase (Postgres/Auth/Storage via
`supabase init`/`supabase start` in infra/), a hand-written 0001_init.sql migration covering
extensions, the frozen taxonomy enums (category groups, six-value formality scale), an
updated_at trigger function, and RLS conventions (no product tables yet), a FastAPI app with
a single GET /health route proving the app boots and can reach the database, and CI
(.github/workflows/ci.yml) gating both backend (ruff, mypy, pytest, lint-imports) and
frontend (eslint, tsc --noEmit, next build) stacks, plus a .importlinter contract and local
pre-commit config. No product endpoints, no UI, no salvaged AI code, no ports.py. The
critical constraint: the package must be importable (`python -c "import whattowear"`) with
zero environment variables set — database engine creation must be lazy/injected, never at
import time, unlike the legacy db.py this replaces. Full context is in
docs/handoffs/002-backend-foundation.md."

## User Scenarios & Testing *(mandatory)*

This slice has no end user and no UI. Its "user" is a contributor to this repository, and
its "product" is a reproducible local backend that every later, user-facing slice (003
onward) is built against. Independent testability here means a scripted sequence of shell
commands succeeds, not a screen a person clicks through.

### User Story 1 - Clone to running backend (Priority: P1)

A contributor clones the repository, follows a written quickstart, and ends up with a
FastAPI backend running locally against a local, reproducible Postgres database — without
being handed any manually-configured state or a shared cloud resource.

**Why this priority**: Every data-driven feature from 003 onward is blocked until this
exists. Nothing else in the roadmap can be built, demoed, or reviewed without it.

**Independent Test**: On a machine with Docker and `uv` installed, run the two commands the
quickstart specifies (roughly: start the local database, then run the app) and observe the
health endpoint report a reachable database. No product feature is required to verify this.

**Acceptance Scenarios**:

1. **Given** a fresh clone with no `.env` file, **When** the contributor copies
   `.env.example` to `.env` (its placeholder values already match a stock local Supabase
   instance) and runs the app, **Then** `GET /health` returns healthy and reports the
   database as reachable.
2. **Given** the local database has never been initialized, **When** the contributor runs
   the database reset command, **Then** the schema is created from scratch with no manual
   steps and no errors.
3. **Given** the package has no environment configured at all, **When** the contributor runs
   `python -c "import whattowear"`, **Then** the import succeeds without raising — importing
   the package must never require a database connection.

---

### User Story 2 - A pull request is gated on both stacks (Priority: P2)

A contributor opens a pull request against this repository and sees automated checks run
against both the backend and the frontend before merge is possible, catching lint, type and
test regressions without a human reviewer having to run them locally.

**Why this priority**: Without CI, every later slice can silently regress this one. This is
the mechanism that keeps the foundation trustworthy as the codebase grows, but it is not
load-bearing for a single contributor working alone the way User Story 1 is.

**Independent Test**: Open a pull request that touches only backend files and confirm the
backend checks run and report a result; open one that touches only frontend files and
confirm the frontend checks run and report a result. Introduce one deliberate lint failure
on each side in a scratch branch and confirm the corresponding check fails.

**Acceptance Scenarios**:

1. **Given** a pull request that changes a backend file, **When** CI runs, **Then** lint,
   type-check, test and import-boundary checks all execute and their results are visible on
   the pull request.
2. **Given** a pull request that changes a frontend file, **When** CI runs, **Then** lint,
   type-check and build checks all execute and their results are visible on the pull
   request.
3. **Given** a change that imports an AI module (e.g. `pipeline/`, `retrieval/`, `scoring/`)
   from a framework module (e.g. `api`, `main`, `fastapi` itself), **When** CI runs, **Then**
   the import-boundary check fails and names the violation.

---

### User Story 3 - The schema is a checked-in artifact, not tribal knowledge (Priority: P3)

A contributor (or a later feature) can read one migration file and know exactly what
foundation-level database objects exist — extensions, the frozen taxonomy as enforced types,
the timestamp convention, and the access-control convention every future table follows —
without needing to inspect a running database or ask someone who remembers.

**Why this priority**: This is what makes 004 onward buildable without renegotiating
conventions per table. It matters less on day one than User Stories 1 and 2, but its absence
is exactly the kind of cost that compounds silently.

**Independent Test**: Read `infra/supabase/migrations/0001_init.sql` alone, with no other
context, and confirm it fully explains what foundation objects exist and what convention new
tables must follows.

**Acceptance Scenarios**:

1. **Given** an empty local database, **When** the migration is applied, **Then** the six
   category-group values and the six formality values from the frozen taxonomy exist as
   enforced database types, not as application-level string checks alone.
2. **Given** the migration file, **When** a later feature adds its first real table, **Then**
   it can follow a written row-level-security convention already established in this
   migration rather than inventing one.

### Edge Cases

- What happens when `DATABASE_URL` (or any other required setting) is missing at request
  time rather than at import time? The app must fail with a clear, actionable error at the
  point a database-backed request is served — never silently, and never by crashing on
  import.
- What happens when the local Supabase stack is not running at all and a contributor runs
  the app anyway? `GET /health` must report the database as unreachable rather than the
  process crashing or hanging.
- What happens when `supabase db reset` is run against a database that already has the
  schema applied? It must reproduce the same end state from empty, since that is the
  definition of "reproducible" this slice is judged against.
- What happens when someone adds a second migration file later? The convention (ordering,
  naming, one hand-written SQL file per change) must already be evident from this first one.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The backend MUST be an importable Python package requiring zero configuration
  or environment variables to import — `python -c "import whattowear"` MUST succeed with no
  environment variables set.
- **FR-002**: The backend MUST expose exactly one HTTP route, `GET /health`, which reports
  both that the process is running and whether its configured database is currently
  reachable.
- **FR-003**: Database connectivity MUST be established lazily, on first use behind a
  function, and a session MUST be handed to code that needs one rather than imported as a
  shared, module-level object.
- **FR-004**: The local database MUST be provisioned entirely through a local Supabase
  stack (Postgres, Auth, Storage) running in Docker, with no dependency on any cloud-hosted
  project.
- **FR-005**: The database schema MUST be defined by one hand-written, version-controlled
  migration file that a database reset applies from empty to reproduce the identical schema
  every time.
- **FR-006**: The initial migration MUST encode the frozen item taxonomy (the six category
  groups and the six-value formality scale) as enforced database types, not as
  comments or application-only validation.
- **FR-007**: The initial migration MUST establish a reusable `updated_at` trigger
  convention and a written row-level-security convention that later tables are expected to
  follow, without creating any product table itself.
- **FR-008**: Continuous integration MUST run on every pull request and on every push to the
  `rebuild` branch, and MUST gate both the backend stack (lint, type-check, tests, import
  boundaries) and the frontend stack (lint, type-check, build) independently.
- **FR-009**: Continuous integration MUST enforce, automatically, that no framework-facing
  backend module (the HTTP layer) is imported by any AI-facing module — a violation MUST
  fail the pull request, not merely be discoverable by manual review.
- **FR-010**: No secret or credential MUST be committed to the repository. Exactly one
  environment-variable template, listing every variable the backend reads with placeholder
  values, MUST be tracked.
- **FR-011**: A single written quickstart MUST allow a new contributor to go from a fresh
  clone to a running backend against the local database using no information not contained
  in that document.
- **FR-012**: This slice MUST introduce no product-facing HTTP endpoint (closet, outfit,
  styling, or otherwise), no user interface change, no AI/retrieval/scoring code, and no
  interface or abstraction (such as a repository or port) that has no concrete implementation
  or caller yet.

### Key Entities

This slice defines no product data entities (no wardrobe item, outfit, or user profile row).
It establishes the foundation-level database objects every later entity will be built on:

- **Category group** (enforced type): one of `top`, `bottom`, `full_body`, `outerwear`,
  `footwear`, `accessory` — the frozen taxonomy's slot grouping.
- **Formality level** (enforced type): one of `casual`, `smart_casual`, `business_casual`,
  `semi_formal`, `formal`, `black_tie` — the frozen taxonomy's six-value scale.
- **Row-level-security convention**: a documented, repeatable pattern (not a concrete table)
  that every table added from feature 004 onward applies to scope rows to their owning user.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A contributor with Docker and `uv` already installed goes from a fresh clone to
  a `GET /health` response reporting a reachable database in two commands, using only the
  written quickstart, in under ten minutes.
- **SC-002**: Resetting the local database from empty reproduces an identical schema every
  time, with zero manual intervention, on 10 out of 10 attempts.
- **SC-003**: Importing the backend package succeeds with no environment variables set, on
  every attempt, with no exceptions.
- **SC-004**: A pull request that only breaks a backend lint/type/test/import-boundary check
  is blocked by CI before merge, and a pull request that only breaks a frontend
  lint/type/build check is likewise blocked, in both cases without a human reviewer needing
  to run the check locally.
- **SC-005**: Zero real secrets appear anywhere in the repository's tracked history for this
  slice; exactly one tracked file documents every environment variable the backend reads.

## Assumptions

- Docker and `uv` are already installed on any machine this is built or run on; installing
  them is not part of this slice's quickstart.
- "Local Supabase" means the `supabase` CLI's local development stack running in Docker
  containers on the contributor's own machine — never a cloud-hosted Supabase project. A
  cloud project is explicitly out of scope until a deployed environment is needed.
- This slice hand-writes exactly one migration file, scoped to foundation objects (database
  extensions, the two frozen-taxonomy enums, the `updated_at` trigger function, and the
  RLS convention as written guidance). No product table (wardrobe items, outfits, users) is
  created here — those arrive with the features that need them (004 onward).
- Alembic, or any second migration system, is not used; Supabase's own migration mechanism
  is the only one, per the constitution's Technology Constraints.
- `ports.py` and any repository-pattern abstraction over the database is explicitly deferred
  to feature 007, where the AI modules that need it exist. Introducing it now with no caller
  would be the speculative abstraction the constitution's Quality Bar prohibits.
- The single `GET /health` route is the only HTTP surface this slice exposes. It is
  infrastructure-facing (used by contributors and, later, deployment tooling), not a
  product feature.
- "Contributor" in the user stories above stands in for the "user" the spec template
  expects even though this slice has no end-user-facing behavior — this is called out
  explicitly rather than forcing an artificial end-user story onto infrastructure work.
