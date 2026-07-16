# CLAUDE.md

Guidance for Claude Code (and any fresh session) working in this repo.

## What this is

**What to Wear** — an AI personal styling agent. Grounded-assembly RAG: given a
user's wardrobe + a context (occasion, mood, weather), it assembles an outfit
**from items they already own**, obeying rules retrieved from a fashion
knowledge base, and cites those rules. Solo project; course capstone that may
become a product. Backend only so far (`backend/`); `frontend/` is empty until
design lands.

## Read these first (in this order)

1. **`docs/SDD-HANDOFF.md`** — the authoritative plan: current state, the
   5-feature roadmap, known debt, and what's next. Start here every session.
2. **`.specify/memory/constitution.md`** — the non-negotiable rules. Treat as
   binding. Changing it requires an explicit amendment (see its Governance
   section), not a quiet edit.
3. **`specs/<feature>/`** — the full spec/plan/research/tasks for each shipped
   or in-progress feature (e.g. `specs/001-closet-persistence/`).

`docs/what_to_wear_build_plan.md` is **superseded** (pre-constitution
brainstorm, wrong taxonomy/paths/auth) — do not follow it; it's kept for
historical reference only.

## This is a spec-driven project (Spec Kit)

Features run through the Spec Kit workflow: `/speckit.specify` →
`/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.analyze` →
`/speckit.implement`. (Tasks before analyze, not after: the `speckit-analyze`
skill hard-requires `tasks.md` to exist — `check-prerequisites.sh
--require-tasks` errors out otherwise, since analyze cross-checks spec + plan +
tasks together. Confirmed directly in the 002 session; if you see the reverse
order elsewhere, this is the corrected one.) Don't skip `/speckit.analyze`, and
read it like a critic — the planner over-builds; hold it to the constitution's
simplicity rule.

## Session workflow (planner / worker split)

This project is run as **one planning conversation + a fresh session per feature
(or per Feature-002 phase)**. The durable source of truth is the **repo**
(`docs/SDD-HANDOFF.md`, `specs/`, git, the memory files) — not any single chat.
So:

- **A worker session** picks up the next item from SDD-HANDOFF, runs it through
  the spec-kit workflow, and **on completion MUST write state back** — this is
  the handoff contract, not optional:
  1. Update `docs/SDD-HANDOFF.md`: the feature table + "current state" (and
     "Known debt" if you closed or added any).
  2. Update the **"Current state" section in this file (CLAUDE.md)**.
  3. Mark the feature's `specs/<feature>/tasks.md` items `[X]`.
  4. Add a memory if a real decision was made (see the memory index).
  Skip this and the next session starts from stale state and creates conflicts.
- **A planner session** (e.g. deciding the next feature) must **re-read
  SDD-HANDOFF + `git log` first** — don't plan from stale in-context memory, a
  worker session may have moved things since.

## Current state (keep this in sync as features land)

- **Feature 001 (closet-persistence): DONE, merged to `main`.** Per-user closet
  + shared catalog in Postgres (Supabase), JWT auth (ES256/JWKS), full CRUD.
  `context_assembler.load_wardrobe()` reads Postgres now, not the JSON fixture.
- **Feature 002 (styling-agent), broadened + phased — Phase 1 DONE and merged
  to `main`.** Auth-gated `/recommend` behind the JWT dependency (closing the
  cross-user leak — `user_id` now comes from the verified `sub`, not the
  body) and backfilled unit tests for the deterministic pipeline (`colors.py`,
  `cite.py`, `categories.py`, `pipeline/query_builder.py`, `eval/properties.py`)
  + a `/recommend` auth test. **Phases 2–4 (deterministic scoring → LangGraph
  + `/suggest` → refinement) — resuming now** (were paused behind Feature 003,
  now the highest-priority remaining work: this is the actual agent/selection
  logic, and neither 003 nor 004 build it). Full spec/plan/tasks in
  `specs/002-styling-agent/`; resume at task T008 (Phase 2).
  See SDD-HANDOFF Step 3.
- **Feature 003 (mvp-app), redefined from "closet-ingestion" — code complete,
  not yet deployed.** Full spec-kit cycle run on branch `003-mvp-app`.
  Backend: additive `pattern`/`fit` migration, CORS middleware, `vision.py`
  (VLM photo→attribute extraction) + `storage.py` (Supabase Storage upload,
  caller's own bearer token, no service key), two new endpoints
  (`POST /wardrobe/items/extract`, `POST /wardrobe/items/upload`) — parallel
  to, not replacing, the existing catalog-add path. `/recommend`,
  `/wardrobe/items` CRUD, and JWT auth all reused unchanged. 149 existing +
  11 new backend tests pass, ruff clean. Frontend: first code in
  `frontend/` — Next.js app (App Router, TypeScript) covering all 4 required
  user stories (sign-in/up, add-by-photo, view closet, get a suggestion),
  consuming the backend's OpenAPI schema for types (constitution Principle
  VII — generated and verified, not hand-maintained). typecheck/lint/build
  clean; smoke-tested against a locally running backend. **Remaining: 3
  manual, owner-only steps** — create the Supabase Storage `wardrobe-photos`
  bucket + RLS policy, deploy backend to Railway, deploy frontend to Vercel
  (`specs/003-mvp-app/tasks.md` T010/T037/T038/T039) — no coding session has
  the dashboard access these need. **Also remaining, deliberately paused:
  visual polish** — three styling passes (ad hoc CSS, then the Nocturne
  design system's own component classes, then tracing exact colors out of
  `design/What to Wear.dc.html`'s render logic) still didn't match
  expectations; stopped rather than keep iterating without a way to
  actually see it rendered. Full narrative:
  `docs/003-mvp-app-implementation-report.md` (local, untracked). See
  SDD-HANDOFF Step 4.
- **Feature 004 (preference-memory) — DONE, code complete on branch
  `004-preference-memory`, not yet merged to `main`.** Full spec-kit cycle
  run. Closed the gap `set_preference()`/`get_profile()` were defined but
  never called/backed by anything durable: reactions (`POST
  /preferences/feedback`) now persist to Postgres (`suggestion_feedback` +
  `preference_signal_dismissal`, migration `0003`), a pure `derive_signals()`
  function (`memory/preferences.py`) computes rejected colors/avoided
  categories/formality drift with a net-count threshold, and
  `memory/store.py`'s `get_profile()` derives from that instead of an
  `InMemoryStore` — `profile_note(user_id)`'s signature/behavior are
  unchanged, so `pipeline/run.py`/`pipeline/generator.py` needed **zero**
  changes, exactly as planned. Three more endpoints (`GET /preferences`,
  `DELETE /preferences/signals/{signal_key}`, `DELETE /preferences`) plus a
  frontend reaction affordance and a `/preferences` view. **One thing the
  plan didn't anticipate**: `set_preference()`'s free-form key/value API had
  no equivalent under the new derive-only model, so it was removed outright
  (its one caller, `eval/test_users.py`'s manual debug tool, was updated to
  match). 181 backend tests pass (162 pre-existing + 19 new), ruff clean,
  eval no-regression gate passed (this feature touches no retrieval/
  generation code). Full detail: SDD-HANDOFF Step 5.
- **Working in parallel, in separate git worktrees (from 2026-07-16):**
  Feature 002 (resuming Phases 2–4) and Feature 004 are being developed at
  the same time, each in its own worktree
  (`/home/fateme/Projects/w2w/what-to-wear-002`,
  `/home/fateme/Projects/w2w/what-to-wear-004`) attached to their existing
  branches — not the same shared directory. See SDD-HANDOFF's "Working in
  parallel" note for the conflict-risk assessment. **If you're a fresh
  session reading this from one of those worktree directories: you're
  already in the right place, don't `cd` back to the main repo directory or
  switch branches out from under the other session.** **Update: Feature 004
  finished (2026-07-16)** — the conflict-risk assessment held, it never
  touched `pipeline/run.py`/`pipeline/generator.py`/`scoring/`. Merge
  `004-preference-memory` to `main` whenever convenient; check whether the
  002 worktree session is still active before touching its branch.
- **Next after these two land**: the 3 manual deploy steps for Feature 003
  (Supabase Storage bucket, Railway, Vercel — still not done, see Feature
  003 above), then Feature 005.
- **Environment gotcha found while finishing Feature 004**: a fresh `git
  worktree add` only copies tracked files — `backend/data/` (gitignored:
  golden set, KB corpus, wardrobe fixture) was entirely absent from this
  worktree, breaking `test_seed.py` and the eval harness with
  `FileNotFoundError` until copied over from a sibling checkout that has
  it. If a fresh worktree session hits that error, this is why.

## The rules that bite hardest (full text in the constitution)

- **The LLM never selects clothing items.** Item selection is deterministic
  pruning/combination/scoring (Principle 2). Scoring for outfit quality is pure
  Python, reused unchanged in the eval harness (Principle 5). An LLM *judge*
  score may be reported as an edge signal but never drives selection.
- **Style KB gates wardrobe retrieval** — KB queried first, returns structured
  directives, never parallel (Principle 3).
- **Grounded output only** — every item in a suggestion exists in the closet or
  catalog; every rationale cites a retrieved rule_id or scorer output.
- **No-regression gate** — after any change touching retrieval/generation,
  re-run the eval harness and compare against `backend/artifacts/eval_runs/`.
- **Schema is frozen** (Principle 6): category groups
  `top/bottom/full_body/outerwear/footwear/accessory`, six-value formality enum
  (`casual`…`black_tie`), warmth **0–5**, seasons, hex colors. Don't introduce a
  parallel numeric formality scale or rename groups.
- **Simplicity over abstraction** — no repository patterns / service layers /
  ABCs unless two concrete implementations exist today.

## Commands (run from `backend/`)

```bash
uv sync --group dev                      # install incl. pytest/ruff
uv run alembic upgrade head              # apply migrations (needs DATABASE_URL)
uv run python -m whattowear.crud seed-catalog        # one-time catalog seed
uv run python -m whattowear.crud seed-eval-baseline  # eval baseline user's closet
uv run uvicorn whattowear.api:app --reload           # API + Swagger at /docs
uv run pytest tests/ -q                  # unit + integration tests
uv run ruff check . && uv run ruff format .          # lint + format
uv run python -m whattowear.eval.harness # no-regression eval gate
```

Env: `cp backend/.env.example backend/.env` and fill it — needs the gateway
keys (`AI_GATEWAY_API_KEY`, `TAVILY_API_KEY`, `COHERE_API_KEY`), the Qdrant
cloud URL/key, **and** `DATABASE_URL` + `SUPABASE_URL` (the app raises without
the DB vars). Full run/architecture detail: `backend/README.md`.

## Gotchas a fresh session will hit

- **Tests run against the real Supabase database**, isolated per-test by a
  rolled-back transaction fixture (`backend/tests/conftest.py`) — there is no
  separate test DB. They're slower than mocks and need network + real DB creds.
- **The eval harness makes many external calls and is flaky under transient
  network drops** (Qdrant/Cohere/gateway resets). `retrieval_recall` is the
  deterministic metric to compare across runs; the generation-dependent checks
  drift run-to-run from LLM sampling — that's not a regression. Don't declare a
  regression from a single failed or partial run.
- **`/recommend` is now auth-gated** (Feature 002 Phase 1): it depends on
  `get_current_user_id` and derives `user_id` from the verified JWT `sub` — the
  request body no longer carries a `user_id`. A call without a bearer token gets
  401. (It's still slated to give way to `/suggest` in Phase 3.)
- **Supabase pooler (port 6543)** doesn't support server-side prepared
  statements — the engine disables them; migrations prefer the direct 5432 URL
  when reachable. See `specs/001-closet-persistence/research.md`.
- **Node.js isn't preinstalled in a fresh sandbox** (confirmed in the Feature
  003 session). No passwordless sudo either. Install via nvm (user-level, no
  root): `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh
  | bash && nvm install --lts`. If the coding tool runs each command through a
  single long-lived shell process (rather than a fresh login shell per
  command), edits to `~/.zshenv`/`~/.zshrc` made *after* that process started
  won't take effect for the rest of the session — prefix Node/npm commands
  with `export PATH="$HOME/.nvm/versions/node/<version>/bin:$PATH"` instead of
  relying on shell-startup-file sourcing.
- **`frontend/lib/api-types.ts` needs a reachable backend to (re)generate** —
  `npm run fetch:openapi` curls `/openapi.json` from a *running* instance
  (local `uvicorn` or the deployed Railway URL). There's no way to generate
  it from static source alone; start the backend first.
- **The Supabase Storage `wardrobe-photos` bucket + its per-user RLS policy
  is a manual, one-time dashboard step** (Feature 003), not something any
  migration or seed script creates — see `specs/003-mvp-app/quickstart.md`
  Prerequisites. `storage.py` will fail every upload until this exists.

## Git

Commit per logical unit with clear messages. Don't push or merge unless asked.
Keep history clean (no noise merges). `gh` is not installed in some
environments — offer the web PR flow when that's the case.
