# Handoff — Feature 002: Backend and database foundation

**From:** tech lead · **Status:** ready to start · **Branch:** cut from `rebuild`

This slice has no user interface and nothing to look at. It is the foundation every
data-driven feature stands on, and it is the last chance to get the shape right cheaply.
Feature 001 did this for the frontend; this is its counterpart.

---

## 1. Mission

Stand up the Python package, the local database, and the CI that gates both stacks. **No
product endpoints, no UI, no salvaged AI code.**

Done means: someone clones the repo, runs two commands, and has a working backend against a
reproducible local database, with CI proving it.

---

## 2. How to run this

Start from `rebuild`. Cut `002-backend-foundation` yourself — no hook does it for you.

```
/speckit-specify → /speckit-clarify → /speckit-plan → /speckit-tasks
                 → /speckit-analyze → /speckit-implement
```

`plan-template.md` carries the ten Constitution Check gates. Most will be N/A for this
slice — say so explicitly and say why, one line each. The ones that bite are **X**
(documents are data) and the Technology Constraints section.

---

## 3. Read first

| # | Source | What to take |
|---|---|---|
| 1 | `.specify/memory/constitution.md` | Binding. **Technology Constraints** fixes your layout, tooling and migration system. |
| 2 | `docs/legacy-ai-inventory.md` §3, §6 | The measured coupling problem you must not reproduce, and what the stack actually is. |
| 3 | `docs/feature-plan.md` | Where this slice sits and what depends on it. |
| 4 | `../app-legacy/backend/` | Read-only. `db.py`, `config.py`, `models.py`, `alembic/versions/` are the reference. |

`../app-legacy` is a checkout of the live prototype. **Never modify anything in it.**

---

## 4. In scope

### 4.1 Python package

`backend/src/whattowear/` — src layout, package name `whattowear`, exactly the structure in
the constitution's Technology Constraints. `pyproject.toml` driven by `uv`, Python 3.12.

Create the package skeleton with `__init__.py` files, but **only implement**:

- `core/config.py` — settings from environment, no literal secrets, no `~` or absolute
  local paths anywhere.
- `core/logging.py` — structured logging.
- `core/db.py` — session management. **Read §6 before writing this file.**
- `main.py` — FastAPI app with one route: `GET /health`, proving the app boots and can reach
  the database.
- `.env.example` — every variable the app reads, with placeholder values. This is the only
  env file that is ever tracked.

### 4.2 Database

- `supabase init` into `infra/`, producing `infra/supabase/`.
- `supabase start` — Postgres, Auth and Storage in Docker. Docker is installed and running.
- `infra/supabase/migrations/0001_init.sql`, **hand-written**.

**Scope of `0001_init.sql`: foundation only, no product tables.** Extensions, the frozen
taxonomy from Principle VI as Postgres enums (the six category groups, the six-value
formality scale), an `updated_at` trigger function, and the RLS conventions every later
table will follow. Feature 004 adds `wardrobe_items`, 010 adds outfits, and so on — each
slice brings its own migration.

Use the legacy `alembic/versions/` files as a **checklist of what existed**, not as
something to replay. Four tables existed there; replaying them would reintroduce the old
structure through the back door.

### 4.3 CI

`.github/workflows/ci.yml`, on `pull_request` and on push to `rebuild`:

- **Backend:** `ruff`, `mypy`, `pytest`, `lint-imports`
- **Frontend:** `eslint`, `tsc --noEmit`, `next build`

Add `.importlinter` with the AI-independence contract from the constitution. The AI modules
it names do not exist yet, so declare a contract that **passes today** against the modules
that do exist, and leave a comment saying feature 007 extends `source_modules` as each
module lands. A contract that errors on missing modules is worse than a narrow one.

Add `pre-commit` locally.

---

## 5. Explicitly out of scope

Any product endpoint (closet, outfits, styling) · any salvaged AI code · `ports.py` — it
belongs to 007, where the modules that need it arrive and their Protocols are knowable ·
authentication (003) · the corpus manifest and ingestion (007) · any frontend change ·
**any cloud Supabase project.** Local only. A cloud project gets created when a deployed
environment is first needed, not before.

Defining a Protocol with no implementation and no caller is speculative abstraction, which
the constitution's Quality Bar prohibits. Resist it.

---

## 6. Traps

**1. Do not reproduce the legacy `db.py` import-time engine.** This is the single most
important thing in this brief.

`../app-legacy/backend/src/whattowear/db.py` calls `create_engine()` at module import time
and raises if `DATABASE_URL` is unset. Three AI modules import it. The measured consequence,
recorded in `docs/legacy-ai-inventory.md` §3, is that you cannot import the pipeline — to
run a unit test or an eval — without a configured database.

Build lazy, injected session management from the start: an engine created on first use
behind a function, never at module scope, and a session handed in rather than imported. The
whole package must be importable with no environment at all.

**2. Carry the pooler knowledge, do not rediscover it.** Legacy `db.py` documents a real,
expensive lesson: Supabase's transaction pooler (port 6543, Supavisor) does not support
server-side prepared statements or session-level state. It sets `prepare_threshold=None` and
`NullPool` to avoid "prepared statement already exists" errors. That reasoning is sound and
should carry forward — read the file's docstring before writing yours.

**3. Alembic is not used.** Legacy runs it; the constitution drops it. Supabase migrations
are the only migration system, because Alembic cannot express RLS policies, storage buckets
or auth configuration — most of what this schema actually is. Do not install it, and do not
port `alembic/env.py`.

**4. `supabase db reset` from empty is the real test.** Not "the migration applied once on
my machine." If a reset from an empty database does not reproduce the schema exactly, the
schema is not reproducible and this slice is not done.

**5. RLS is not optional and does not come free.** The legacy code has no RLS anywhere. Every
table added from feature 004 onward carries per-user policies. Establish the convention here,
in `0001_init.sql` and in writing, so later slices follow a pattern instead of inventing one.

**6. No secrets, ever.** Only `.env.example` is tracked. The local Supabase keys `supabase
start` prints are development-only and still do not belong in a tracked file.

---

## 7. Definition of done

- [ ] `uv sync` then `uv run pytest` passes from a clean clone.
- [ ] `python -c "import whattowear"` succeeds **with no environment variables set.** This
      is the regression test for trap 1.
- [ ] `supabase db reset` succeeds from an empty database and reproduces the schema.
- [ ] `GET /health` returns healthy and reports database reachability.
- [ ] `ruff`, `mypy`, `pytest` and `lint-imports` all clean locally.
- [ ] CI runs green on a pull request, covering both stacks.
- [ ] `.env.example` lists every variable the app reads. No real secret anywhere in the diff.
- [ ] A new contributor can go from clone to running backend using only `quickstart.md`.

---

## 8. If you hit a gap

The constitution fixes the layout and the tooling; it does not decide everything. If you hit
a genuine decision it does not cover — connection pooling strategy, migration naming, test
database handling — make the call, **record it in `research.md` with the alternatives you
actually considered**, and flag it in your report.

That last part is not ceremony. Feature 001 shipped one defect, and its cause was a
decision record whose "alternatives considered" list was missing the option that turned out
to be correct. The reasoning was sound; the option set was incomplete. When you write that
section, ask yourself what you have not listed.
