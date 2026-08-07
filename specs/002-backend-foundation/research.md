# Research: Backend and database foundation

Phase 0 output. Every decision below is a genuine judgment call the constitution and the
handoff (`docs/handoffs/002-backend-foundation.md`) left open. Each is recorded with the
alternatives actually considered, per the handoff's §8 instruction — Feature 001's one
shipped defect traced to an "alternatives considered" list that was missing the option that
turned out correct, so the bar here is a real comparison, not a rubber stamp.

## 1. Import-time safety for config and DB (constitutional trap 1)

**Decision**: No module-level `Settings()` instantiation and no module-level
`create_engine()`. `core/config.py` exposes a `get_settings()` function wrapped in
`functools.lru_cache`; `core/db.py` exposes a `get_engine()` function, also
`lru_cache`-wrapped, that calls `get_settings()` and `create_engine()` internally. Both are
called for the first time only when a request actually needs them — inside the FastAPI
dependency (`get_session`), never at import time. `python -c "import whattowear"` therefore
never touches `os.environ` for a required variable.

**Rationale**: this is the literal regression test in the brief (trap 1) and the definition
of done. `lru_cache` gives the "create once, reuse" behavior the legacy module-level engine
had, without paying for it at import time.

**Alternatives considered**:
- *Module-level engine exactly like legacy `db.py`.* Rejected — this is the trap itself.
- *Lazy engine, but eager `Settings()` at module level with all-optional fields.* Rejected:
  it would make `import whattowear` succeed, but it silently defers the "did you configure
  this" question past the point where a developer expects an error, since a `Settings()`
  instance would exist and look valid with `database_url=None` until something tries to use
  it three call-frames later. An explicit `get_settings()`/`get_engine()` pair keeps "not
  configured yet" and "configured wrong" as the same, single, well-located failure point.
- *A FastAPI `lifespan` context manager that creates the engine at app startup instead of
  first request.* Considered and adopted as a refinement: `main.py`'s lifespan calls
  `get_engine()` once at startup (not import), so the first real request isn't the one that
  pays connection-setup cost, and the process still fails fast at startup if genuinely
  misconfigured, at *app-run* time rather than *import* time — the two are different, and
  the brief only forbids the latter.

**Correction found during implementation — driver scheme.** `DATABASE_URL` is written in
the ordinary `postgresql://` form (matching what `.env.example` and `supabase status` both
print), but SQLAlchemy resolves that bare scheme to the psycopg2 dialect, which this project
never installs — it only depends on psycopg3. `get_engine()` rewrites the scheme to
`postgresql+psycopg://` before calling `create_engine()`, exactly as legacy `db.py` did
(`url.replace("postgresql://", "postgresql+psycopg://", 1)`). This was in the legacy
reference read during planning but didn't make it into the first implementation pass; caught
by actually running the server against the local database rather than only unit-testing the
lazy-construction behavior in isolation.

## 2. Connection pooling strategy

**Decision**: Carry forward legacy's `NullPool` + `prepare_threshold=None` unconditionally
— for every environment, not only when a pooler is detected. `DATABASE_URL` always points at
the Supabase transaction pooler (port 6543 in a hosted project; the local CLI's pooler
emulation, below, locally).

**Rationale**: legacy's docstring (research.md → "Supabase transaction pooler") already
paid for this lesson: transaction-mode pooling doesn't support server-side prepared
statements or session-level state. `NullPool` avoids a long-lived server-side session;
`prepare_threshold=None` disables psycopg3's prepared statements. Applying it unconditionally
means dev, CI and production all exercise the exact same connection behavior — there is no
"pooler-safe" code path that only gets tested in production for the first time.

**Alternatives considered**:
- *Detect pooler vs. direct connection from the URL and switch pool class.* Rejected —
  two code paths means the one used in production is the one least exercised locally, which
  is exactly the coupling problem the legacy inventory flagged as a lesson worth carrying,
  not rediscovering.
- *Use SQLAlchemy's default `QueuePool`.* Rejected — this is what produces "prepared
  statement already exists" errors against Supavisor; it is the failure mode the legacy
  docstring documents.

## 3. Local Supabase pooler emulation

**Decision**: Enable the local pooler in `infra/supabase/config.toml`
(`[db.pooler] enabled = true`, port `54329`, `pool_mode = "transaction"` — the CLI's
default values once enabled) rather than leaving it disabled and connecting to the direct
database port (`54322`). `.env.example`'s `DATABASE_URL` points at `54329`.

**Rationale**: `supabase init` generates the pooler section disabled by default (verified by
running `supabase init` in a scratch directory — see the generated `config.toml`). Leaving
it disabled would mean local dev and CI never exercise the transaction-pooler behavior
Decision 2 defends against, and the first real test of that code path would be a production
incident. Enabling it locally makes local dev, CI and production identical in this respect.

**Alternatives considered**:
- *Leave the pooler disabled locally, connect directly on 54322.* Rejected for the reason
  above — it's the cheaper setup but defeats the purpose of carrying the pooler lesson
  forward at all.
- *Point `DATABASE_URL` at 54322 for local/CI and only use the pooler URL in the deployed
  environment via a separate variable.* Rejected — two different `DATABASE_URL` shapes
  between environments is exactly the kind of divergence Decision 2 is trying to eliminate.

**Correction found during implementation — local pooler tenant identifier.** `supabase
start`/`supabase status`'s printed `DB_URL` is always the *direct* connection (port 54322),
never the pooler one, even with `[db.pooler] enabled = true`. Connecting to 54329 with plain
`postgres` as the username fails: `(ENOIDENTIFIER) no tenant identifier provided`. The local
CLI's Supavisor container registers its one local tenant under the fixed name `pooler-dev`
(confirmed both by reading the pooler container's own startup log — "Deleting all dist cache
for tenant pooler-dev" — and by successfully connecting), so the pooler username must be
`postgres.pooler-dev`, not `postgres` and not `postgres.<project_id>` (the latter was the
first guess, and fails too — `(ENOTFOUND) tenant/user postgres.whattowear not found`). This
is not documented in the CLI's own `status` output or in `config.toml`'s comments; it was
found by reading container logs after the naive connection string failed. `.env.example` and
`quickstart.md` carry the corrected form
(`postgresql://postgres.pooler-dev:postgres@127.0.0.1:54329/postgres`).

## 4. Supabase CLI distribution

**Decision**: Track the CLI as a pinned `devDependency` in a new `infra/package.json`
(`"supabase": "2.110.0"`, exact pin), invoked as `npx supabase <command>` from `infra/`.
CI installs the same pinned version via the official `supabase/setup-cli@v2` GitHub Action.

**Rationale**: Supabase does not support a global `npm install -g supabase`; their
documented install path is either a per-OS package manager or a project-local
`devDependency`. This repo has no root `package.json` (only `frontend/` does), and
`infra/supabase/` is where `supabase init` writes its output, so scoping the CLI dependency
to `infra/` keeps it next to what it manages instead of bleeding into `frontend/`'s
dependency tree or inventing a root-level Node project for one tool.

**Alternatives considered**:
- *Root-level `package.json` for tooling.* Rejected — the constitution's layout is fixed
  (`frontend/`, `backend/`, `infra/`, `design/`, `docs/`); a root Node project isn't in that
  list and isn't needed for one CLI dependency.
- *Unpinned `npx supabase@latest`.* Rejected — an unpinned CLI can silently change local
  Postgres major version or config schema between runs, which is precisely what makes
  "reproducible from empty" (DoD item 3) hard to guarantee over time.
- *Homebrew/apt system package.* Rejected — not reproducible across contributors' machines
  the way a committed, pinned dependency file is; also doesn't match how CI would install it.

## 5. Postgres major version

**Decision**: Accept the CLI's current default (17) rather than pinning an older version.

**Rationale**: there is no existing hosted Supabase project yet (this slice explicitly
creates none — local only), so there is no "must match the remote" constraint the config
file's own comment warns about. Using the current default is the simplest correct choice
until a cloud project exists, at which point that project's version becomes the pin.

**Alternatives considered**:
- *Pin to the version the legacy prototype's hosted project uses.* Rejected — that project
  belongs to `app-legacy` (read-only, a different Supabase project entirely) and this slice
  explicitly creates no cloud project of its own to match it against.

## 6. Database extensions in `0001_init.sql`

**Decision**: Enable `pgcrypto` only.

**Rationale**: `pgcrypto` provides `gen_random_uuid()` with certainty across supported
Postgres versions (it is core-builtin from PG13+, but Supabase's own generated migrations
conventionally enable it explicitly rather than depending on version-specific core
behavior) and is the extension every later feature's `id uuid default gen_random_uuid()`
primary key will want. No other extension (full-text search, `uuid-ossp`, PostGIS, etc.) has
a concrete caller yet.

**Alternatives considered**:
- *Enable nothing; defer to feature 004 when the first product table needs a UUID
  default.* Rejected — extensions are exactly the kind of foundation-layer, low-risk,
  widely-shared object the brief scopes into this migration ("Extensions, the frozen
  taxonomy … an updated_at trigger function, and the RLS conventions"). Deferring it means
  feature 004 has to touch a "foundation" migration that this slice's whole purpose was to
  finish.
- *Enable `uuid-ossp` instead/also.* Rejected — `pgcrypto`'s `gen_random_uuid()` is the
  modern, maintained path; `uuid-ossp` is legacy and redundant once `pgcrypto` is present.

## 7. RLS convention: what gets written now vs. wired later

**Decision**: `0001_init.sql` documents the convention as SQL comments — the exact
`ENABLE ROW LEVEL SECURITY` / `CREATE POLICY … USING (auth.uid() = user_id)` shape every
future per-user table follows — without enabling RLS on, or creating, any table (there is
none to enable it on yet). The mechanism that populates `auth.uid()` for a request made
through the backend's own connection (as opposed to Supabase's PostgREST data API, which
populates it automatically) is explicitly out of scope here and flagged for feature 003
(Auth) to wire.

**Rationale**: the brief is explicit that RLS is a convention to establish "in `0001_init.sql`
and in writing," not a feature to implement against a table that doesn't exist. Writing a
policy with no table to attach it to isn't valid SQL; a written comment convention plus this
research note is the honest way to satisfy "establish the pattern" without inventing a table
or faking a policy.

**Alternatives considered**:
- *Create a placeholder table just to demonstrate the RLS policy shape.* Rejected —
  this is a real product table with no product behind it, which is the same category of
  speculative-abstraction violation as an unimplemented `ports.py`. The constitution's
  Quality Bar prohibits exactly this.
- *Skip documenting RLS entirely in this migration and leave it to feature 004.* Rejected —
  the brief calls this out by name as something 004 onward must follow "instead of
  inventing one," which requires the convention to already be written down before 004
  starts.

## 8. Test database handling in CI

**Decision**: CI's backend job runs a real local Supabase stack — `supabase start` from
`infra/`, then `supabase db reset` (proving DoD item 3 on every PR, not just once on a
developer's machine) — and points `pytest` at the resulting local `DATABASE_URL`. No
mocking of the database layer for the `/health` integration test.

**Rationale**: the DoD explicitly requires `supabase db reset` to succeed "from an empty
database," and the brief's trap 4 says the real test is a reset from empty, not "applied
once on my machine." The only way CI actually proves that on every PR is by doing it, not
by trusting a developer to have done it locally before opening the PR. GitHub's
`ubuntu-latest` runners have Docker available, which is all `supabase start` needs.

**Alternatives considered**:
- *Mock the database layer in tests, skip a real Postgres in CI.* Rejected — it would let a
  broken migration or a broken `core/db.py` merge without CI ever noticing, defeating the
  entire point of this slice's CI gate.
- *Use a plain `postgres:17` service container instead of the full Supabase stack.*
  Rejected — it would validate the migration SQL but not the pooler behavior (Decision 2/3)
  or the overall "does `supabase start` + `db reset` actually work" claim the DoD makes,
  which is specifically about the Supabase CLI workflow, not generic Postgres.

## 9. Structured logging approach

**Decision**: Python's standard-library `logging` module configured for JSON output via a
small custom `logging.Formatter` subclass in `core/logging.py` (no new third-party
dependency). A single `configure_logging()` function is called once, from `main.py`'s
lifespan startup — not at import time.

**Rationale**: the brief asks for "structured logging," not a specific library, and the
legacy `logging_utils.py` this replaces (26 lines) was a thin wrapper around the standard
library too. Adding a dependency (e.g. `structlog`) for one formatter is more than this
slice's one call site justifies; it can be revisited if a later feature's needs outgrow it.

**Alternatives considered**:
- *`structlog`.* Rejected for now — real value (contextvars-based request-scoped fields,
  processor pipelines) that this slice has no caller for yet; would be dependency weight
  with no measured problem it solves, which the Quality Bar's simplicity rule flags.
- *Plain unstructured `logging.basicConfig`.* Rejected — doesn't satisfy "structured," and
  every later feature would either have to fix it or add to the mess.

## 10. `core/config.py` scope for this slice

**Decision**: `Settings` (via `pydantic-settings`) exposes only what this slice's own code
reads: `database_url: str`, `log_level: str = "INFO"`, `environment: str = "development"`.
It does **not** carry forward legacy `config.py`'s LLM-gateway settings (`AI_GATEWAY_*`,
`WTW_CHAT_MODEL`, `LANGSMITH_API_KEY`, etc.) — those have no caller in this slice.

**Rationale**: the legacy inventory maps legacy `config.py` → `core/config.py` as a single
adaptation, but that mapping describes the AI-layer port (feature 007), which is where those
settings get a real caller again. Adding them here would be exactly the "no salvaged AI
code" boundary the brief draws, plus unused settings fields with no reader — the Quality
Bar's "no caller" test for speculative abstraction applies to config fields as much as to
Protocols.

**Alternatives considered**:
- *Port the full legacy `Settings` shape now so feature 007 doesn't have to touch
  `core/config.py` again.* Rejected — every field would be dead until 007, and 007 is
  explicitly the slice that ports AI modules; extending `core/config.py` there is the
  correct home for that change, not a preemptive copy here.

## 11. CI job shape

**Decision**: Two independent jobs in `.github/workflows/ci.yml` — `backend` and
`frontend` — both triggered on `pull_request` and on `push` to `rebuild`, both running
unconditionally (no path filtering to skip one stack based on which files changed).

**Rationale**: path-filtered CI is a common optimization, but it trades a small amount of CI
time for a real gap: a backend-only PR that happens to break a frontend type-generation
contract (Principle VII, coming in a later slice) would merge green. This slice is small
enough that both jobs running always costs little and closes that gap from day one.

**Alternatives considered**:
- *Path-filter each job to its own stack's changed files (`paths:` trigger filters).*
  Rejected for the cross-contract-risk reason above; can be revisited later if CI runtime
  becomes a real cost, at which point it's a CI-only change with no impact on this slice's
  scope.
