# Quickstart: backend + local database

Prerequisites: Docker running, `uv` installed, Node.js/`npm` installed (for the pinned
Supabase CLI only — the backend itself has no Node dependency).

## One-time setup

```bash
cd infra && npm install
```

Installs the pinned Supabase CLI (`research.md` §4) as a local dependency. Nothing else to
configure before the two commands below.

## The two commands

**1. Start the local database:**

```bash
cd infra && npx supabase start
```

Boots Postgres, Auth and Storage in Docker and applies every migration under
`infra/supabase/migrations/` — including `0001_init.sql` — to a fresh database.

The printed `DB URL` is the **direct** connection (port 54322) — not what this project uses.
Build the pooler URL yourself: same host and password, port **54329**, and the username is
`postgres.pooler-dev` (the local CLI's Supavisor tenant is always named `pooler-dev` — not
documented in `supabase status`'s output; see research.md §3's correction note for how this
was found):

```
postgresql://postgres.pooler-dev:postgres@127.0.0.1:54329/postgres
```

That's the value `.env.example`'s `DATABASE_URL` already has as its placeholder.

**2. Run the backend:**

```bash
cd backend && uv sync && cp .env.example .env
uv run uvicorn whattowear.main:app --reload
```

`.env.example`'s `DATABASE_URL` placeholder is already the correct local pooler URL (fixed
password, fixed local port, fixed tenant) — nothing to paste in for a stock local Supabase
instance. Only edit it if your local stack's password or ports were customized.

Then:

```bash
curl -s localhost:8000/health | jq
# {"status": "ok"}
```

If `supabase start` wasn't run first, or was later stopped, the same request returns
`{"status": "unhealthy", "failed_dependencies": ["database"]}` with a `503` — see
`contracts/health.md`.

## Proving the database is reproducible from empty

The definition-of-done claim this slice makes is that a reset from empty reproduces the
schema exactly — not "it worked once":

```bash
cd infra && npx supabase db reset
```

## Everything else

```bash
cd backend
uv run pytest                 # unit + integration tests
uv run ruff check .           # lint
uv run mypy src               # types
uv run lint-imports            # AI-independence contract (.importlinter)
```

```bash
uv run pre-commit install     # once per clone, from backend/ or repo root — see .pre-commit-config.yaml
```

## Regression test this slice exists to satisfy

```bash
env -i python3 -c "import sys; sys.path.insert(0, 'backend/src'); import whattowear"
```

Must succeed with **zero** environment variables set (`env -i`). This is trap 1 from the
handoff, made executable.
