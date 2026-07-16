# CLAUDE.md

Guidance for Claude Code (and any fresh session) working in this repo.

## What this is

**What to Wear** — an AI personal styling agent. Grounded-assembly RAG: given a
user's wardrobe + a context (occasion, mood, weather), it assembles an outfit
**from items they already own**, obeying rules retrieved from a fashion
knowledge base, and cites those rules. Solo project; course capstone that may
become a product. Backend in `backend/`; `frontend/` has a working Next.js app
(Feature 003) covering sign-in, add-by-photo, closet view, and get-a-suggestion
(now against `/suggest`, Feature 002 Phase 3) — not yet deployed publicly.

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
- **Feature 002 (styling-agent), broadened + phased — ALL PHASES DONE
  (2026-07-16), not yet merged to `main`.** Phase 1 (auth-gate `/recommend`,
  unit-test backfill) was already merged. Phases 2–4 built in this worktree:
  - **Phase 2 — `scoring/` package**: four deterministic dimension scorers
    (color harmony, formality coherence, weather fitness, silhouette
    balance) + a swappable combination strategy (FR-009a), imported
    unchanged into both the graph and `eval/harness.py` via one shared
    `scoring.score_outfits()` call (Principle V — never forked).
  - **Phase 3 — `pipeline/graph.py` + `POST /suggest`**: the linear pipeline
    became an 8-node LangGraph `StateGraph`; `wardrobe_retrieval` prunes on
    hard constraints before generation ever sees the closet (k=8/slot);
    `score_and_rank` is the only ranking step. `/recommend` and
    `pipeline/run.py` are **deleted** — `/suggest` (SSE) is the sole
    suggestion entrypoint, and the frontend (`app/suggest/page.tsx`,
    `components/SuggestionResult.tsx`) is cut over to it (a hand-rolled SSE
    parser in `lib/api-client.ts`, since `EventSource` doesn't support
    POST). `eval/harness.py` now runs the golden set through the compiled
    graph, not the retired `run_pipeline`.
  - **Phase 4 — refinement**: `memory/store.py`'s checkpointer is now
    Postgres-backed (see Gotchas below for a real prepared-statement issue
    hit here). "Warmer"/"less formal"/"alternatives" are deterministic
    keyword-parsed deltas that shift `wardrobe_retrieval`'s pruning bounds
    or exclude prior item-sets — never touching `ctx` itself, so unstated
    constraints survive a refinement turn (FR-013). An optional
    reported-only LLM judge score (`eval/judge.py`, FR-010) is opt-in via
    `harness.py --judge`, off by default.
  - Full eval no-regression gate green after every phase touching
    retrieval/generation (per-case `retrieval_recall` byte-identical to the
    archived baseline throughout). Full narrative, including two real bugs
    found via live end-to-end testing (not just unit tests) and fixed:
    SDD-HANDOFF Step 3.
  - **Not done**: merging to `main` — all commits are on `002-styling-agent`
    in this worktree; worth deciding whether to PR each phase separately
    (the original branch-strategy note) or as one PR now that everything's
    done.
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
- **Working in parallel, in separate git worktrees (from 2026-07-16):**
  Feature 002 (this worktree — all phases now done, see above) and Feature
  004 (`/home/fateme/Projects/w2w/what-to-wear-004`) were developed at the
  same time on their own branches — not the same shared directory. **If
  you're a fresh session reading this from this worktree: you're already in
  the right place, don't `cd` back to the main repo directory or switch
  branches out from under another session working in a sibling worktree.**
  The 3 manual deploy steps for Feature 003 (Supabase Storage bucket,
  Railway, Vercel) are still outstanding too, but need dashboard access no
  coding session has.
- **⚠️ Feature 004 finished and merged to `main` while Feature 002 Phase
  2-4 was still in progress in this worktree.** `002-styling-agent` is now
  based on a stale `main` and merging it back **will produce 9 real
  conflicts**, including `memory/store.py` and `api.py` — both features
  independently rewrote parts of `memory/store.py` (002: Postgres
  checkpointer; 004: preference-profile derivation). Verified via
  `git merge-tree --write-tree` (dry-run, nothing changed) — see
  SDD-HANDOFF's callout under the feature table for the full file list.
  **Nobody has done this merge yet.** Don't treat it as a formality; budget
  a dedicated session for it, and re-run the full test suite + eval gate
  after resolving, before pushing.

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
- **`/recommend` no longer exists** (Feature 002 Phase 3, T037a) — deleted along
  with `pipeline/run.py` once `/suggest` was verified equivalent and the
  frontend confirmed cut over. `POST /suggest` (SSE, auth-gated the same way
  `/recommend` used to be — `get_current_user_id`, `user_id` from the verified
  JWT `sub`, never the body) is the sole suggestion entrypoint now.
- **Supabase pooler (port 6543)** doesn't support server-side prepared
  statements — the engine disables them; migrations prefer the direct 5432 URL
  when reachable. See `specs/001-closet-persistence/research.md`. **This bit a
  second component in Feature 002 Phase 4**: `langgraph-checkpoint-postgres`'s
  `PostgresSaver.from_conn_string` hardcodes `prepare_threshold=0` (prepare on
  first use) and reproduced the same "prepared statement does not exist"
  failure — even against `DATABASE_URL_DIRECT`, not just the pooler. Fixed in
  `memory/store.py` by connecting manually with `prepare_threshold=None`
  instead of using `from_conn_string`.
- **A fresh `git worktree add` does NOT carry over gitignored files** —
  `backend/data/` (KB source + `golden_set.yaml`) and `backend/artifacts/
  eval_runs/` are both gitignored, so a new worktree starts with neither and
  the eval harness can't run at all until they exist. Copy them from an
  existing checkout (`rsync -a` from the main worktree's `backend/data/` and
  `backend/artifacts/eval_runs/`) — confirmed necessary setting up this
  worktree for Feature 002 Phases 2-4.
- **LangGraph checkpoint deserialization warns on the project's own Pydantic/
  dataclass types** (`Context`, `ScoredOutfit`, `SuggestResult`, `GenOutput`,
  `RetrievalResult`, `WardrobeItem`) — `Deserializing unregistered type ...
  This will be blocked in a future version`. Still works today (Feature 002
  Phase 4's refinement checkpointing); a future `langgraph-checkpoint-postgres`
  upgrade may require registering these via `allowed_msgpack_modules`. Not
  done — flagged for whoever upgrades that dependency next.
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
