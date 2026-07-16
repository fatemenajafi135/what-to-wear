# What to Wear: Spec-Driven Development Handoff

## Where the project stands

Monorepo. `backend/` holds all Python. `frontend/` is empty — design has
landed (`/design`, committed) and frontend build starts with Feature 003 (see
Step 4). Baseline is committed to `main`. Spec Kit is initialized.

**Already built and working. Do not rewrite:**
- `backend/src/whattowear/retrieval/` : baseline, hybrid, advanced retrievers
- `backend/src/whattowear/ingest/` : loaders, chunkers, KB build, wiki refine
- `backend/src/whattowear/kb.py` : style knowledge base
- `backend/src/whattowear/pipeline/` : query_builder, context_assembler, generator, cite,
  **graph** (Feature 002 Phases 2-4 — `pipeline/run.py` retired, `graph.py` is now the
  sole pipeline entrypoint via `POST /suggest`)
- `backend/src/whattowear/scoring/` : deterministic dimension scorers + combination strategy
  (Feature 002 Phase 2) — reused unchanged by both the graph and the eval harness
- `backend/src/whattowear/external/` : weather, trends
- `backend/src/whattowear/memory/store.py` : Postgres-backed checkpointer (Feature 002 Phase 4)
  + in-memory profile/history store
- `backend/src/whattowear/eval/` (incl. `judge.py`, optional/opt-in) and `backend/evals/` : Ragas plus LLM judge
- `backend/data/golden_set.yaml`, `backend/artifacts/eval_runs/*.jsonl` : evaluated results
  (gitignored — not carried into a fresh `git worktree add`; copy from an existing
  checkout if a new worktree needs them, as this session did)
- **Feature 001 (closet-persistence), done**: `backend/src/whattowear/db.py`,
  `models.py`, `crud.py`, `auth.py`, `backend/alembic/` — persistent per-user
  closet + shared catalog in Postgres (Supabase), JWT auth (ES256/JWKS), full
  CRUD (`GET`/`POST`/`POST .../bulk`/`PATCH`/`DELETE` on `/wardrobe/items`,
  `GET /catalog/items`). `context_assembler.load_wardrobe()` reads Postgres
  instead of the JSON fixture, which is now catalog-seed-only. No change to
  retrieval behavior — verified via the eval no-regression gate.
- **Feature 002 (styling-agent), all phases done** (2026-07-16, not yet
  merged): `POST /suggest` (SSE) is the sole suggestion entrypoint —
  `/recommend` deleted. Deterministic scoring, LangGraph pipeline,
  conversational refinement. See Step 3 below for the full narrative.

**Not built yet:**
1. ~~LangGraph agent graph.~~ **Done, Feature 002 Phase 3.**
2. ~~Deterministic scoring (color harmony, formality coherence, weather fitness, silhouette balance).~~ **Done, Feature 002 Phase 2.**
3. Combinatorial outfit generation engine. **Not built as originally imagined and not needed as scoped**: `generate_outfits` still uses the LLM to assemble candidates from a deterministically-pruned inventory (constitution Principle II is satisfied by pruning-before-generation + deterministic ranking-after, not by replacing the LLM's assembly step with brute-force combinatorics — that was never required).
4. Vision ingestion (photo to item metadata) — **DONE, see Feature 003 below.** `vision.py` + `storage.py` + the two new endpoints.
5. Preference memory from feedback — **DONE, see Feature 004 (Step 5).**
6. Production hardening and deployment — **DONE (code), see Feature 005 (Step 6).** Output grounding guardrail, per-user Redis cache, LiteLLM routing all shipped. The Railway/Vercel/Supabase-Storage-bucket account setup from Feature 003 is now confirmed working by the owner; the live backend just needs a redeploy of this branch to actually run the new code.
7. Frontend — **DONE (code), see Feature 003 below; cut over to `/suggest` in Feature 002 Phase 3.** `frontend/` now has a working Next.js app covering all 4 required user stories. `/design` (committed) was the visual/component reference, not a pixel port; `docs/design-backend-conflict-report.md` (local, untracked) has the full design↔backend conflict audit that drove Feature 003's scope.

**Known debt — CLEARED by Feature 002, Phase 1 (see Step 3):**
- ~~**`/recommend` is unauthenticated.**~~ **Fixed.** `/recommend` now depends on
  `get_current_user_id` (same JWT dependency as `/wardrobe/items`); `user_id` is
  no longer accepted from the request body — it comes from the verified `sub`
  claim. The cross-user closet leak is closed. (Still superseded by `/suggest`
  in Phase 3, but the live gap is gone now.)
- ~~**The pre-existing deterministic pipeline has no unit tests.**~~ **Fixed.**
  Unit tests backfilled for `colors.py`, `cite.py`, `categories.py`,
  `pipeline/query_builder.py`, `eval/properties.py` (`backend/tests/unit/` +
  one `/recommend` auth integration test), satisfying the Quality Bar's
  "deterministic logic requires unit tests."

## Architecture rules, not negotiable

1. **Style KB gates wardrobe retrieval.** KB is queried first, returns structured
   directives, not prose. Those directives shape the wardrobe query. Never parallel.
2. **Deterministic core, LLM at the edges.** Scoring and generation are pure Python.
   The LLM parses intent and writes rationale. It never picks clothing items.
3. **Grounded output only.** Every item_id in a suggestion must exist in the closet
   or the catalog.
4. **Scoring functions are eval metrics.** Written as code first, reused in the harness.
5. **No regression.** After any feature touching retrieval, re-run evals and compare
   against `artifacts/eval_runs/`.

## Stack, locked

- Python 3.12, uv, FastAPI, LangGraph
- Supabase: Postgres, auth, image storage. Pooler connection, port 6543.
- Qdrant: vectors, hybrid dense plus metadata filter. Keep it. Do not migrate to pgvector.
- Railway: backend container plus Redis
- LangSmith: tracing on every LLM and retrieval call
- Next.js on Vercel, later

## Plan: 5 features, in order

Each runs: /speckit.specify, /speckit.clarify, /speckit.plan, /speckit.analyze,
/speckit.tasks, /speckit.implement

**Workflow:** one planning conversation + a fresh session per feature (or per
Feature-002 phase). On finishing a feature/phase, the worker session **writes
state back** — update this file's table + "current state," update `CLAUDE.md`'s
"Current state," mark `specs/<feature>/tasks.md` done. See the "Session workflow
/ handoff contract" in `CLAUDE.md`. This keeps the planner and worker sessions
from drifting.

| # | Feature | Notes |
|---|---|---|
| 001 | closet-persistence | ✅ **DONE (merged).** Fixture became a real per-user Postgres database + shared catalog + JWT auth. |
| 002 | styling-agent | The big one. Pipeline becomes a graph, plus scoring. **Broadened** to also fold in the recommend-flow cleanup (auth-gate `/recommend`) and unit-test backfill for the deterministic pipeline. Delivered in phases (see Step 3). **✅ ALL PHASES DONE, merged to `main` (2026-07-16).** Phase 1 merged earlier. Phases 2–4 (scoring package, LangGraph `/suggest`, conversational refinement) built in a parallel worktree alongside Feature 004, then merged back — see the merge callout below the table for how the two features' conflicting changes were reconciled. `/speckit.analyze` re-run before resuming Phases 2-4 found and fixed one CRITICAL gap: retiring `/recommend` (T037a) had no dependency on the frontend that actually calls it. Fixed via tasks T036a-d (frontend cutover to `/suggest`) gating T037a — both landed. `/recommend` and `pipeline/run.py` are now deleted; `/suggest` is the sole suggestion entrypoint. Full eval no-regression gate green after every phase touching retrieval/generation, and again after the merge. |
| 003 | **mvp-app** *(redefined — was "closet-ingestion")* | ✅ **Code complete and merged to `main`, deploy pending.** Full spec-kit cycle run (spec/clarify/plan/tasks/analyze/implement). All 4 user stories built and verified locally (backend: 149+11 tests pass, ruff clean; frontend: typecheck/lint/build clean, dev-server smoke-tested against a locally running backend). **3 manual steps remain, owner-only** (need dashboard access no coding session has): create the Supabase Storage `wardrobe-photos` bucket + RLS policy (T010), deploy backend to Railway (T037), deploy frontend to Vercel (T038); then re-run quickstart.md against the public URLs (T039). **Known, explicitly deferred gap: visual polish** didn't fully match `design/What to Wear.dc.html` — see `docs/003-mvp-app-implementation-report.md` (local, untracked). See Step 4 and `specs/003-mvp-app/tasks.md`. |
| 004 | preference-memory | ✅ **DONE and merged to `main`** (finished 2026-07-16, in its own worktree, concurrently with Feature 002's Phases 2-4 above — see the merge callout below the table). Feedback endpoint + derived preference profile + frontend reaction affordance. 29/29 tasks. |
| 005 | production-hardening | ✅ **Code complete, merge-ready; one manual step remains.** Full spec-kit cycle (spec/clarify/plan/tasks/analyze/implement). Output grounding guardrail, per-user Redis cache, LiteLLM routing all built, tested against the real gateway/DB/Redis, and eval-no-regression-gate green. Railway/Vercel/Supabase Storage all confirmed working by the owner, but the live backend is still on pre-005 code — needs a redeploy after merge to validate live (T008). See Step 6. |
| 007 | ai-improvements | ⚠️ **Code complete, live verification NOT done.** Full spec-kit cycle (spec/clarify/plan/tasks/analyze/implement) on branch `007-AI-improvements`. Closes two cert-challenge rubric gaps (a genuine chunked-embedding L1 semantic sub-layer; a live Tavily L3 search replacing a static trend KB) plus a real, previously-diagnosed refinement bug (the "warmer" delta's blanket footwear/accessory exemption replaced with a per-category-relative floor). All three land as pure code changes, fully unit-tested (38 new/updated tests, 193/193 existing `tests/unit` green) — but this session's sandbox had **no `.env` credentials and none of the gitignored `backend/data/` source files** (Wikipedia pages, EPUBs, wardrobe fixture), so the eval no-regression gate, integration tests, the before/after warmth-floor evidence capture, and a LangSmith trace check could not be run. **T032 (the eval gate) is the mandatory next step before merge** — see Step 7 and `specs/007-ai-improvements/tasks.md`'s environment note. |

**How 002 and 004's parallel work was reconciled (2026-07-16).** Both
features were built in separate git worktrees at the same time (see the
branch-strategy note below); 004 finished and merged to `main` first, so by
the time 002's Phases 2–4 were ready, `main` had moved. A pre-merge
`git merge-tree --write-tree` dry-run flagged 9 likely-conflicting files;
the actual merge produced 10 (`schema.py` and `eval/test_users.py` also
conflicted, not predicted ahead of time). Of those, 8 were mechanical
(docs, `.specify/feature.json`, generated frontend types — regenerated or
rewritten, not hand-merged) or purely additive (`schema.py`: both features
only appended new Pydantic models, no overlap). Two needed real
reconciliation:
- **`memory/store.py`**: 002 replaced the module-level `InMemorySaver`
  checkpointer with a lazy `get_checkpointer()` (Postgres-backed when
  reachable, Phase 4's refinement-thread durability). 004 replaced
  `get_profile()`'s in-memory backing with a Postgres-derived aggregation
  and deleted `set_preference()` entirely. These touch disjoint functions
  in the same file — both kept in full, no actual behavior tradeoff.
- **`api.py`**: 002 replaced `/recommend` with `/suggest` (SSE); 004 only
  *added* four new `/preferences/*` endpoints after the existing ones. The
  endpoint bodies didn't overlap at all (git auto-merged them); only the
  shared import block needed a manual union.

One conflict wasn't just mechanical merging — it was a real latent bug the
merge surfaced: 002's `eval/test_users.py` `__main__` block still called
`seed_test_user_memory()` → `memory.set_preference()`, a function 004 had
deleted outright on `main` (the whole point of 004's redesign — preferences
are derived from real feedback only, never injected directly). Resolved by
keeping 002's graph-based invocation (`pipeline.run` no longer exists to
fall back to) and dropping the now-dead seeding call, matching 004's
already-established approach for that file. Full test suite + ruff +
frontend typecheck/lint/build + eval no-regression gate re-run after
resolving, before the merge commit.

**Branch strategy note (002 only):** Feature 002 is large enough to run as a
multi-phase effort rather than one merge. Each phase merges to `main` on its
own PR when its eval no-regression gate is green — the *feature* is the
umbrella, the *phases* are the mergeable units. This keeps the gate honest and
avoids a long-lived branch drifting from `main`; work can pause after any phase
(e.g. to start 003/004) and resume without conflict. The other features keep
the default one-feature-one-branch flow.

**Why 003 jumped ahead of 002's remaining phases:** a design prototype
(`/design`) landed and the required-scope deadline (referred to throughout
this doc as "the MVP milestone requirements" — see `docs/mvp-milestone.md`,
local/untracked) only strictly needs a working, publicly-reachable browser
app, not the deterministic-scoring/LangGraph rebuild. A design↔backend
conflict audit (`docs/design-backend-conflict-report.md`, local/untracked)
found the actual blocking gaps were: no frontend, no auth screen, no
photo-based add-item path, no deployment — none of which 002's remaining
phases address. So: 003 is redefined to close exactly those gaps, minimally,
using the already-working `/recommend` for suggestions rather than waiting on
`/suggest`. 002 Phases 2–4 resume after 003 ships. **Feature 003 is developed
vertically** (backend + frontend together, per capability slice — sign-in,
then add-item, then closet view, then suggest — not backend-then-frontend)
since that's what actually produces a demoable increment at each step, and it
surfaces contract mismatches (like the ones the conflict report found)
immediately instead of at integration time.

## Step 0: Constitution

Run `/speckit.constitution` with the appendix text below.

Then read `.specify/memory/constitution.md` and confirm two clauses survived the
reformatting: "Existing pipeline is authoritative" and "Style knowledge gates
wardrobe retrieval". Those two do the most work downstream. If they got softened,
edit the file directly. Commit it.

## Step 1: Converge

`/speckit.converge`

Let it read `backend/` and report. Check its output against the "Not built yet" list.

Red flag: if it proposes rewriting the retrievers or the eval harness, principle 1
did not land. Fix the constitution before writing any spec.

## Step 2: Feature 001, closet-persistence

> ✅ **DONE (merged to `main`).** Full spec, plan, tasks, and outcome live in
> `specs/001-closet-persistence/`. All 4 user stories + polish shipped; 58
> tests against the live database; eval no-regression gate passed.
>
> The `/speckit.specify` / `/speckit.plan` prompts below are kept **verbatim as
> the historical record of what was pasted** — clarify/research then corrected
> two things (which is exactly what those steps are for):
> - **Taxonomy:** the draft's "slot (top, bottom, one-piece, outer, shoes,
>   accessory)" and "formality 1 to 5" conflicted with the frozen constitution
>   schema. Shipped with the constitution's taxonomy instead: category groups
>   `top/bottom/full_body/outerwear/footwear/accessory`, the six-value formality
>   enum, warmth **0–5**, and slot *derived* from category (not a stored field).
> - **Auth:** "verifying the Supabase JWT using the service key" was corrected —
>   the shipped auth verifies the JWT signature locally via the project's JWKS
>   endpoint (ES256), holding only the public key. The service key is never used
>   for user-token verification. See `specs/001-closet-persistence/research.md`.

/speckit.specify:

    A user's closet is persistent, private to them, and editable.

    A user can view their closet, add an item by picking from a shared pre-built
    catalog, correct any attribute of an item, and remove an item. Accessories are
    first-class items alongside clothing.

    Every item carries a slot (top, bottom, one-piece, outer, shoes, accessory), a
    category within that slot, colors with hex values, a fabric, a warmth rating
    1 to 5, a formality rating 1 to 5, and applicable seasons.

    Existing wardrobe retrieval must read from this persistent closet instead of
    the fixture file, with no change to retrieval behaviour or eval scores.

    Photo upload is out of scope. Catalog selection is the only way to add items.

Then /speckit.clarify. Answer carefully. It will poke at the taxonomy, which is
the point. The taxonomy is expensive to change later.

/speckit.plan, add:

    Start from the existing backend/src/whattowear/schema.py. Add SQLAlchemy models
    plus Alembic migrations against Supabase. Keep the existing Qdrant collection
    contract unchanged. Wardrobe retrieval reads Postgres for hard filters and
    Qdrant for ranking. Seed the shared catalog from data/fixtures/wardrobe.json.
    Auth is a FastAPI dependency verifying the Supabase JWT using the service key.
    Row-level security stays off for now.

Then /speckit.analyze, /speckit.tasks, /speckit.implement.

Gate before merging: re-run the eval harness. Scores must match
artifacts/eval_runs/. If they moved, something broke.

## Step 3: Feature 002, styling-agent

> **Spec-driven cycle run.** Full spec/clarify/plan/tasks/analyze artifacts live in
> `specs/002-styling-agent/` (spec.md, research.md, data-model.md,
> `contracts/suggest.md`, quickstart.md, tasks.md). Phase 1 was implemented
> *before* this cycle was run (as pure hardening, per the original plan below);
> the cycle was then run retroactively to give it spec/task traceability and
> prospectively to plan Phases 2–4. `/speckit.analyze` found and the resulting
> edits fixed one CRITICAL gap (the graph path wasn't wired into the
> golden-set/eval-harness gate the constitution's Quality Bar requires) plus five
> lower-severity findings — see `specs/002-styling-agent/tasks.md` T032a and its
> Notes.
>
> **`/speckit.analyze` re-run 2026-07-16, before resuming Phases 2–4** (paused
> behind Feature 003, now resuming in parallel with Feature 004, each in its
> own git worktree). Found one more CRITICAL gap, this time from environment
> drift rather than an internal inconsistency: `plan.md` said "no frontend
> work this feature — `frontend/` stays empty," true when Feature 002 was
> planned and false since Feature 003 shipped a real frontend that calls
> `/recommend`. Task T037a (retire `/recommend`) had zero dependency on that
> frontend. Fixed: `tasks.md` T036a-d (SSE-consumption helper, regenerated
> OpenAPI types, cut the frontend's suggest page + result component over to
> `/suggest`, manual verification) now gate T037a — `/recommend` can't be
> retired until the live product is confirmed still working against
> `/suggest`. `plan.md`'s Constitution Check (Principle VII row), Project
> Type line, and Project Structure section corrected to match.
>
> The `/speckit.specify` / `/speckit.plan` prompts below are kept
> **verbatim as the historical record of what was pasted**; clarify then
> corrected/narrowed the MVP scope (see below) — same pattern as Feature 001.
> - **Body shape**: deferred entirely out of this feature (no persistent
>   profile store); silhouette balance uses general proportion principles only.
> - **Catalog substitution**: deferred entirely — an unfillable required slot
>   omits the outfit, it is never filled from the shared catalog this feature.
> - **Score-combination strategy (FR-009a)**: shipped as a swappable unit (one
>   default, equal-weighted average, plus a documented alternative) rather than
>   a single locked formula, since which combination is "best" is itself
>   something to evaluate, not decide up front.
>
> **Phases 2–4 implemented and all green (2026-07-16); merged to `main`
> 2026-07-16** (see the merge callout under the feature table above for how
> this reconciled with Feature 004's concurrent changes).
> - **Phase 2 (scoring)**: `scoring/` package — four pure dimension scorers +
>   `combine.rank_outfits` (default equal-weighted average, one documented
>   alternative), imported unchanged into both the graph and `eval/harness.py`
>   (Principle V — one shared `score_outfits()` call site, no fork). Eval
>   gate: per-case `retrieval_recall` byte-identical to the archived baseline.
> - **Phase 3 (graph + `/suggest`)**: `pipeline/graph.py` — the eight-node
>   `StateGraph` (research.md order), `wardrobe_retrieval` prunes on hard
>   constraints before generation ever sees the closet (k=8/slot cap),
>   `score_and_rank` is the only ranking step (LLM never ranks).
>   `eval/harness.py` now runs the golden set through the compiled graph, not
>   the old linear `run_pipeline` (one entrypoint, not two). A real gap
>   `/speckit.analyze` caught mid-build: `generator.py`'s prompt said "Return
>   1-2 outfits" — pre-dated FR-002/SC-003's 3-5 requirement and nothing
>   downstream could satisfy it without this one-line prompt fix. Frontend
>   cutover (T036a-d) shipped in the same phase: a hand-rolled SSE parser in
>   `api-client.ts` (`EventSource` doesn't support POST),
>   `SuggestionResult.tsx` now renders all four `DimensionScore`s +
>   `rank_score` per outfit. `/recommend` and `pipeline/run.py` deleted only
>   after the frontend cutover was verified against the real compiled graph
>   (no browser-automation tool available in-session, so this substituted for
>   literal click-through — flagged as still worth a human spot-check).
> - **Phase 4 (refinement)**: `memory/store.py`'s checkpointer is now
>   Postgres-backed (`DATABASE_URL_DIRECT` preferred over the pooler — even
>   `PostgresSaver.from_conn_string`'s default reproduced db.py's own
>   documented "prepared statement does not exist" failure, so the connection
>   is built manually with `prepare_threshold=None`, same mitigation).
>   `RefinementTurn` isn't a stored object — it's checkpointer-persisted
>   `GraphState` fields (`original_context`/`last_result`/
>   `refinement_deltas`) LangGraph already carries across same-`thread_id`
>   invokes. "Warmer"/"less formal" shift `wardrobe_retrieval`'s pruning
>   bounds (never `ctx` itself); "alternatives" excludes `last_result`'s
>   item-sets; an unsatisfiable refinement falls back to `last_result` with a
>   `note` (FR-015). Real end-to-end testing against the live closet fixture
>   found and fixed a real bug: the warmth floor applied to *every* category
>   including footwear/accessories, which this closet's footwear can't
>   satisfy — starved those slots and forced the FR-015 fallback far more
>   than intended; now exempt. Optional reported-only LLM judge score
>   (`eval/judge.py`, FR-010) is opt-in via `harness.py --judge` (off by
>   default — extra LLM call per case); an architectural unit test walks
>   `scoring/*.py`'s AST to assert none of them import it, so "never
>   influences ranking" isn't just a docstring promise.
> - **Known forward-compat note, not yet acted on**: LangGraph's checkpoint
>   serializer warns `Deserializing unregistered type ... This will be
>   blocked in a future version` for the project's own Pydantic/dataclass
>   types (`Context`, `SuggestResult`, `GenOutput`, `RetrievalResult`,
>   `WardrobeItem`, `ScoredOutfit`) on every checkpoint read. Still works
>   today; a future langgraph-checkpoint-postgres upgrade may require
>   registering these types explicitly (`allowed_msgpack_modules` per the
>   warning text) — not done here, out of this feature's scope.
> - **Merged**: Phases 2-4 landed on `main` as one merge commit rather than
>   separate per-phase PRs (the original branch-strategy note) — by the time
>   they were ready, Feature 004 had already merged concurrently and
>   produced real conflicts (`memory/store.py`, `api.py`), so reconciling
>   all three phases against `main` in one dedicated merge session was
>   simpler than three separate conflict resolutions.

**Scope (broadened).** Beyond the original "pipeline becomes a graph + scoring,"
Feature 002 also absorbs two things that have no other home: the recommend-flow
cleanup (auth-gate `/recommend`, eventually replaced by `/suggest`) and the
unit-test backfill for the pre-existing deterministic pipeline. See "Known debt"
above.

**Delivery: phased, each phase merges to `main` on its own PR** (see the branch
strategy note under the plan table). Do the essential phases first; it's fine to
pause after any phase, go do 003/004, and come back. Every phase touching
retrieval/generation re-runs the eval no-regression gate before merge.

- **Phase 1 — essentials (no behavior change, mergeable alone). ✅ DONE.** Gated
  `/recommend` behind the same JWT dependency as `/wardrobe/items` (closed the
  live cross-user leak — `user_id` is now the verified JWT `sub`, never a body
  field). Backfilled unit tests for `colors.py`, `cite.py`, `categories.py`,
  `pipeline/query_builder.py`, `eval/properties.py` (78 new tests in
  `backend/tests/unit/`) plus a 2-test `/recommend` auth integration file. Pure
  hardening — no new product surface. No retrieval/generation change, so the
  eval gate was not re-run (nothing it measures changed). Tasks T001–T007 in
  `specs/002-styling-agent/tasks.md`.
- **Phase 2 — deterministic scoring.** New `src/whattowear/scoring/` package:
  color harmony, formality coherence, weather fitness, silhouette balance — pure
  functions, each returning a 0–1 score + a reason string, reused unchanged
  inside the eval harness (constitution Principle 5, "scoring functions are eval
  metrics"), plus the swappable score-combination strategy (FR-009a). Reuse
  `colors.py` for hex handling. Tasks T008–T022.
- **Phase 3 — graph + real selection.** Pipeline → LangGraph (node order in the
  plan prompt below). Deterministic pruning/combination/scoring replaces the
  LLM picking items directly (constitution Principle 2, "the LLM never selects
  items"). `/suggest` (SSE) ships; `/recommend` stays live during the
  transition. An unfillable required slot omits that outfit — **no catalog
  substitution this feature** (deferred, see clarification above). Tasks
  T023–T037, including T032a which wires the new graph path into the
  golden-set/eval-harness gate (a `/speckit.analyze` finding, not in the
  original plan prompt below).
- **Phase 4 — refinement + optional LLM edge signal.** Conversational refinement
  ("warmer", "less formal") via a Postgres checkpointer keyed by thread_id, and
  — if wanted — an LLM *judge* score surfaced **for reporting/eval only**.
  Catalog substitution is explicitly **not** part of this phase or this
  feature — see Future Work in spec.md. Tasks T038–T047.

**Scoring model (decided): deterministic-drives, LLM-as-edge-signal.** The
deterministic scorers are the *only* thing that selects and ranks items. An LLM
score may be computed and reported as an additional signal (and its
agreement/disagreement with the deterministic scores feeds the milestone
writeup's improvements section) but it **never** influences which items are
chosen. This
is fully consistent with constitution Principle 2 ("the LLM never selects
items") and Principle 5 ("no metric exists only inside a prompt") — every metric
still has a deterministic form the harness can check, and the LLM never selects
items — so **no constitution change is required.** (Note: these are the
constitution appendix's numbers 2 and 5, not the condensed "Architecture rules"
list above, which is ordered differently.)

/speckit.specify:

    A user describes what they need in plain English and receives three to five
    complete outfit suggestions from their own closet, each with a written rationale.

    The system accounts for local weather, the occasion and mood in the request,
    the season, and the user's body shape.

    Suggestions follow professional styling principles retrieved from the style
    knowledge base. The retrieved principles determine what is asked of the closet,
    and the rationale is grounded in those same principles.

    Each outfit is scored on separately reportable dimensions: color harmony,
    formality coherence, weather fitness, and silhouette balance. These scores are
    computed by deterministic code, not by a language model.

    If the closet cannot fill a required slot, a similar catalog item is suggested
    and clearly marked as one the user does not own.

    The user can ask for alternatives, and can refine conversationally ("warmer",
    "less formal") without restating the original request.

/speckit.plan, add:

    Graph node order: parse_request, gather_context, style_retrieval, build_query,
    wardrobe_retrieval, generate_outfits, score_and_rank, explain. Style retrieval
    gates wardrobe retrieval, never parallel. Reuse pipeline/query_builder.py and
    pipeline/context_assembler.py as graph nodes rather than rewriting them. New
    deterministic scoring package at src/whattowear/scoring/, reusing colors.py for
    hex handling. Prune with hard constraints (warmth, formality band, season)
    before combining, cap candidates at k=8 per slot, never brute-force the raw
    closet. Postgres checkpointer keyed by thread_id for conversational refinement.
    The /suggest endpoint streams via SSE from the start.

## Step 4: Feature 003, mvp-app (redefined)

**Required now** (each tied to a specific MVP-milestone gap or a hard
dependency of one — see `docs/design-backend-conflict-report.md` §4/§5):

1. **Sign-in/sign-up screen** — every endpoint needs a JWT; blocks everything
   else. No backend work (Supabase Auth). Frontend: minimal, on-theme, built
   from scratch (design has none — the report's finding, not an oversight).
2. **Schema unification** — additive migration adding `pattern` and `fit`
   (nullable, same pattern as `fabric`/`source` in Feature 001); frontend
   shows the *full* 6-value formality enum and all 6 category groups
   (including `full_body`), not the design's narrower mock set. Union of
   what both sides have, not a lowest-common-denominator cut.
3. **Add item by photo, minimal** — camera/gallery capture → one VLM call →
   pre-filled fields → user reviews/edits → save. New backend: Supabase
   Storage upload, one gateway VLM call, a new "create item directly"
   endpoint (`source='upload'`, no `catalog_item_id` — the existing
   catalog-add path is untouched). **Editing reuses the existing `PATCH
   /wardrobe/items/{id}` as-is — zero new backend work for that part.**
   Multi-item-per-photo detection (bounding boxes) is explicitly deferred.
4. **View closet** — frontend only; `GET /wardrobe/items` already works.
5. **Get outfit suggestions, minimal** — frontend calls the existing
   `/recommend` (already JWT-gated post-002-Phase-1), not `/suggest`
   (doesn't exist yet). Free-text "ask me to style you" input, no chat, no
   clarifying questions (a stateless endpoint can't support that turn-taking
   — deferred to 002 Phase 3+ / `/suggest`). **Known, accepted trade-off:**
   the demo's outfit selection is still the LLM picking items directly
   (Principle 2 debt, unchanged by this feature) — fine for the milestone,
   flagged for Task 7's reflection, real fix stays Feature 002 Phases 2–3.
6. **Deploy, publicly reachable** — thin slice only. Backend on Railway
   (already the locked stack), frontend on Vercel (already the locked
   stack, "later" becomes "now"). Not full 005 hardening.

**Deferred, kept in the plan, not dropped** (none are MVP-milestone
requirements): occasion picker (rebuild later using the real
`OCCASION_FORMALITY` vocabulary — `office, job_interview, wedding, date,
brunch, funeral, beach, gala, party` — not the design's Formal/Casual/Sport/
Outdoor, which don't match it); multi-item photo detection; catalog-browse UI
(backend already 100% supports it, `GET /catalog/items` + bulk-add, purely a
future frontend task); chat + conversational refinement (waits on `/suggest`);
streak / saved looks / share / chat history / style-tag persistence (no
backend concept exists for any of these; likely Feature 004 territory,
decided then, not now).

Branch: `003-mvp-app`, off `main`. Full spec-kit cycle
(`/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks`
→ `/speckit.analyze` → `/speckit.implement`) — this is real feature work, not
small/mechanical. Artifacts land in `specs/003-mvp-app/`.

> **Full spec-kit cycle run — code complete, deploy pending.** `spec.md` has
> 4 required P1 user stories (sign in, add-by-photo, view closet, get
> suggestion); quality checklist 16/16, zero `[NEEDS CLARIFICATION]` markers.
> `/speckit.plan` → `research.md`/`data-model.md`/`contracts/`/`quickstart.md`;
> `/speckit.tasks` → 39-task `tasks.md`; `/speckit.analyze` found 7 findings
> (1 HIGH: SC-003 vs. an optional-field contract mismatch; rest MEDIUM/LOW),
> all fixed before implementing. `/speckit.implement` built:
> - **Backend**: additive `pattern`/`fit` migration (0002), CORS middleware,
>   `vision.py` (VLM structured-output extraction, reuses `generator.py`'s
>   pattern), `storage.py` (Supabase Storage upload via the caller's own
>   bearer token, existing `requests` dep, no service-role key), two new
>   endpoints (`POST /wardrobe/items/extract`, `POST /wardrobe/items/upload`).
>   149 existing + 11 new tests pass; ruff clean. `/recommend`,
>   `/wardrobe/items` CRUD, JWT auth all reused unchanged.
> - **Frontend**: first code in `frontend/` — Next.js 16 (App Router,
>   TypeScript), consuming the backend's OpenAPI schema for types
>   (`lib/api-types.ts`, generated and verified against a locally running
>   backend — Principle VII satisfied, not a hand-maintained duplicate).
>   Supabase Auth JS client-side, no new backend auth code. All 4 user
>   stories built: sign-in/up + auth guard, add-by-photo (capture → review/
>   correct → save, with a session-expiry draft-preservation path), closet
>   grid + empty state, free-text suggestion + "closet can't fulfill this"
>   state. typecheck/lint/build clean; dev-server smoke-tested (all routes
>   200) against the local backend.
> - **Not done — 3 manual, owner-only steps** (need external dashboard
>   access no coding session has): create the Supabase Storage
>   `wardrobe-photos` bucket + per-user RLS policy; deploy backend to
>   Railway; deploy frontend to Vercel; then re-run `quickstart.md` against
>   the live URLs. Tracked as `tasks.md` T010/T037/T038/T039.
> - **Not done — visual polish, explicitly deferred.** Three styling passes
>   this session (ad hoc CSS → the Nocturne design *system*'s token/component
>   classes → tracing the actual selected/unselected chip colors out of
>   `design/What to Wear.dc.html`'s own render logic) still didn't match your
>   expectation. You said to stop iterating blind (no browser/screenshot tool
>   was available to verify) and pick it up in a later session — this is a
>   deliberate pause, not a resolved issue. Full narrative of what each pass
>   got wrong and what to try differently: `docs/003-mvp-app-implementation-report.md`
>   (local, untracked).
>
> Full narrative: `docs/003-mvp-app-planning-report.md` (local, untracked).

/speckit.plan, add:

    Frontend: Next.js on Vercel (already the locked stack). Consume the
    backend's OpenAPI schema for types (constitution Principle VII -- no
    hand-maintained duplicate types). Use /design's interactive prototype and
    design-system bundle (_ds/nocturne-.../styles.css) as the visual/component
    reference, not a pixel-perfect port -- the taxonomy corrections from
    docs/design-backend-conflict-report.md override the mock's narrower
    values (full 6-value formality, full 6 category groups, no occasion-
    picker buttons this phase).

    Auth: Supabase Auth JS client directly in the frontend (email/password
    sign-up/sign-in), issuing the same Supabase JWT the backend already
    verifies (ES256/JWKS, unchanged from Feature 001) -- no new backend auth
    code.

    Add-item-by-photo: one new backend flow -- accept an uploaded photo,
    upload it to Supabase Storage (already the locked stack), call the
    existing gateway LLM client (config.py) with a vision-capable model for
    one structured-output extraction call (category/colors/fabric/warmth/
    formality/season/pattern/fit), return the extraction as an unsaved draft
    for the frontend to render editable. A separate new endpoint creates the
    wardrobe item directly from the (possibly user-corrected) attributes --
    source='upload', no catalog_item_id -- parallel to, not replacing, the
    existing catalog-based POST /wardrobe/items. Correcting an already-saved
    item reuses the existing PATCH /wardrobe/items/{id} unchanged.

    Schema: additive Alembic migration adding nullable pattern and fit
    (free-text, matching fabric's shape) to WardrobeItemRow/WardrobeItem/
    WardrobeItemPatch, mirroring exactly how fabric/source were added in
    Feature 001.

    Suggestions: frontend calls the existing /recommend (already JWT-gated
    post-002-Phase-1) as-is -- no backend change. Free-text request field, no
    occasion picker.

    Deploy: backend to Railway, frontend to Vercel (both already the locked
    stack) -- bare public reachability only, not the full 005 hardening
    (LiteLLM gateway, semantic cache, guardrails stay deferred).

## Step 5: Feature 004, preference-memory

> **`/speckit.specify` + `/speckit.clarify` done.** Grounded in an actual read
> of `memory/store.py` first (this step's own note, below, said to run
> `/speckit.converge` first — done by direct inspection instead). Finding:
> the *consumption* side already exists and is already wired into
> `/recommend` (`profile_note()` → `generator.py`), but nothing ever *writes*
> a preference (`set_preference()` is defined but never called), there's no
> feedback endpoint, and everything is in-memory (lost on restart/redeploy).
> This feature targets exactly that gap — **it does not require Feature 002's
> `/suggest`/graph work**, so the original scope note below ("feed into
> parse_request") is corrected: `parse_request` is a Phase-3 graph node that
> doesn't exist yet. This hooks into the currently-live `/recommend` path's
> existing `profile_note` mechanism instead. `spec.md` has 4 user stories (2×P1:
> react to a suggestion, suggestions reflect learned taste; 2×P2: view/clear
> preferences); quality checklist 16/16, zero `[NEEDS CLARIFICATION]`
> markers — two real design forks resolved via documented Assumptions
> (deterministic derivation from structured outfit data, not NLP-parsed
> reasons; no separate persisted Suggestion entity needed). Full narrative:
> `docs/004-preference-memory-planning-report.md` (local, untracked).

Original scope note (feedback endpoint, derive a preference profile from
rejections — rejected colors, avoided categories, formality drift): confirmed
accurate and unchanged by `/speckit.specify`; only the "feed into
parse_request" integration point was corrected, per the banner above.

/speckit.plan, add:

    Persistence: new Postgres tables via SQLAlchemy + an additive Alembic
    migration, matching Feature 001's pattern -- a SuggestionFeedback table
    (user_id, verdict, reason, the reacted-to outfit's item_ids + a snapshot
    of their category/colors/formality at feedback time, created_at). No
    separate materialized "preference profile" table -- compute the derived
    profile on read by aggregating SuggestionFeedback rows, same shape as
    memory/store.py's existing get_profile() but Postgres-backed instead of
    in-memory. Simplicity over abstraction: no cache-invalidation machinery
    for a solo-scale read pattern.

    Swap memory/store.py's set_preference/get_profile (currently
    InMemoryStore-backed) for the Postgres-backed equivalents, keeping
    profile_note(user_id)'s signature and behavior unchanged so
    pipeline/run.py and pipeline/generator.py need zero changes -- the
    consumption side already works, only the storage backing changes.
    remember_interaction/recent_interactions (short-term history) are out of
    scope for this feature -- leave them in-memory, untouched.

    New endpoints: one to record a reaction (verdict + optional reason + the
    outfit's item_ids -- looked up against the user's own wardrobe_items,
    already scoped by the existing auth dependency, to get real attributes;
    no new Suggestion entity), one to view the derived profile, one to clear
    it entirely, one to remove a single derived signal. All reuse the
    existing get_current_user_id JWT dependency, unchanged.

    Frontend: add a reaction affordance (like/reject + optional reason) to
    the existing frontend/components/SuggestionResult.tsx from Feature 003,
    and a new preferences view. Regenerate the OpenAPI-derived types
    (constitution Principle VII) after the new endpoints land, matching how
    Feature 003 did it.

> **Full spec-kit cycle run — code complete, merged.** `/speckit.plan` →
> `research.md`/`data-model.md`/`contracts/preferences.md`/`quickstart.md`;
> `/speckit.tasks` → 29-task `tasks.md` across the 4 user stories;
> `/speckit.analyze` found 2 MEDIUM (soft-influence and explicit-override
> wiring untested) + 2 LOW (a doc gap and a missing manual persistence
> check) findings, all fixed before implementing — spec.md's Key Entities
> now documents the signal-dismissal mechanism, quickstart.md adds a
> restart check, and T014 became a deterministic wiring test. `/speckit.implement` built:
> - **Backend**: additive migration `0003_add_suggestion_feedback.py`
>   (`suggestion_feedback` + `preference_signal_dismissal`, both additive
>   only); `memory/preferences.py`'s `derive_signals()` — a pure,
>   unit-tested function implementing the net-count-threshold + formality-
>   drift + dismissal-filtering algorithm from `research.md`; `crud.py`'s
>   `record_feedback()` (snapshots item attributes at feedback time, upserts
>   on the outfit's item set) and `dismiss_signal()`; four endpoints under
>   `/preferences`. `memory/store.py`'s `get_profile()` now derives from
>   Postgres instead of an `InMemoryStore` — `profile_note(user_id)`'s
>   signature and behavior are byte-for-byte unchanged, so `pipeline/run.py`
>   and `pipeline/generator.py` needed **zero changes**, exactly as planned.
>   **One design gap the plan didn't anticipate**: `set_preference()`
>   (free-form key/value writes) has no equivalent under the derive-only
>   model — removed, and its one caller (`eval/test_users.py`'s manual
>   debug tool) updated to match, since profile seeding there is now
>   superseded by recording real feedback through the actual mechanism.
>   181 backend tests pass (162 pre-existing + 19 new: 13 unit + 16
>   integration across all 4 stories + 3 wiring tests for the
>   `/speckit.analyze` remediation, one folded together), ruff clean, eval
>   no-regression gate passed (retrieval_recall/grounding scores unaffected
>   — this feature touches no retrieval/generation code, only what
>   `profile_note()` is backed by).
> - **Frontend**: `OutfitReaction.tsx` (like/reject + optional reason) added
>   to each outfit card in `SuggestionResult.tsx`; `PreferencesView.tsx` +
>   `app/preferences/page.tsx` (plain-language signal list, remove-one/
>   clear-all, the "nothing learned yet" empty state) — reuses `AuthGuard`
>   automatically via the root layout. `lib/api-types.ts` regenerated
>   against the four new endpoints. typecheck/lint/build clean; dev-server
>   smoke-tested (all routes 200, including the new `/preferences`) — no
>   browser/screenshot tool available in this environment to verify
>   rendering visually, same constraint noted in Feature 003.
> - **Environment note for future sessions in this worktree**:
>   `backend/data/` (gitignored — golden set, KB corpus, wardrobe fixture)
>   was missing entirely from this worktree (a `git worktree add` only
>   copies tracked files) and had to be copied over from the main repo
>   directory before `test_seed.py` or the eval harness could run at all.
>   If a fresh worktree hits `FileNotFoundError` on `data/golden_set.yaml`
>   or `data/fixtures/wardrobe.json`, this is why — copy `backend/data/`
>   from a sibling checkout that has it.

## Step 6: Feature 005, production-hardening

Original scope note (kept as historical record): LiteLLM gateway, semantic
cache on KB retrieval, output guardrail asserting every item_id exists,
full deploy hardening on Railway (beyond the bare deploy already done in
003). Corrected during planning: the cache targets the whole `/suggest`
result (retrieval+generation), not just KB retrieval — LiteLLM's own
per-call semantic cache can't reach retrieval at all (see below).

> **Full spec-kit cycle run — code complete, deploy pending a redeploy.**
> `/speckit.clarify` resolved 4 ambiguities (per-user-only cache scope,
> LangSmith tracing satisfies FR-010, same-provider-only retry, a concrete
> sub-second cache-hit target). `/speckit.plan` → research.md/data-model.md/
> contracts/quickstart.md; `/speckit.tasks` → 25-task `tasks.md` across 4
> user stories; `/speckit.analyze` found and fixed 2 gaps before
> implementing: the spec's own Edge Case about DB/vector-store health
> checks had no FR or task (added FR-012 + a task), and the grounding
> guardrail's original closet-only design was a literal-compliance gap
> against constitution Principle IV ("closet or shared catalog") — widened
> to check both at negligible cost (one more cheap query, no new
> abstraction). `/speckit.implement` built all four user stories:
> - **US2 (grounding guardrail, P2)**: new `pipeline/grounding.py` +
>   `verify_grounding` graph node between `score_and_rank` and `explain`,
>   dropping any outfit whose items aren't in the requester's wardrobe or
>   the shared catalog. Verified against the eval harness: `retrieval_recall`
>   byte-identical to the archived baseline for every shared golden-set
>   case, `owned_only` unaffected — the guardrail never removes a
>   legitimately-grounded outfit.
> - **US3 (per-user Redis cache, P3)**: new `pipeline/cache.py` — an
>   explicit, exact-key cache around the whole `/suggest` graph invocation
>   (not LiteLLM's own semantic cache, which can't reach retrieval and risks
>   fuzzy false-positive matches across different users' closets — a real
>   correctness risk this feature's own Assumptions had already
>   pre-authorized a fallback for). Keyed by the verified user id + normalized
>   context + a full-content wardrobe fingerprint, so any closet edit
>   naturally invalidates a stale entry — no explicit invalidation hook.
>   **Two real bugs found via testing, not assumed upfront**: (1) the cache
>   key's occasion-to-formality lookup used the raw, non-normalized occasion
>   string, silently defeating the normalization it was supposed to provide;
>   (2) a cache hit's `thread_id` was never passed to `graph.invoke`, so the
>   checkpointer had no state for it — a refinement ("warmer") continuing
>   that thread was silently treated as a brand-new conversation. Fixed by
>   seeding the checkpointer on every hit via `graph.update_state(...)`.
> - **US4 (LiteLLM routing, P4)**: `config.py`'s `get_chat_model`/
>   `get_judge_model` now construct `langchain-litellm`'s `ChatLiteLLM`
>   instead of `langchain_openai`'s `ChatOpenAI`, same gateway, giving
>   automatic retry + LangSmith-visible cost/usage. Three of four call sites
>   needed zero changes; `vision.py`'s all-`Optional`-fields extraction
>   schema hit a real gateway incompatibility with `ChatLiteLLM`'s default
>   structured-output handling (Pydantic omits defaulted fields from
>   `required`; the gateway's strict mode rejects that) — two guessed
>   fallbacks (`json_mode`, `json_schema, strict=False`) were tried and
>   rejected by the gateway too before finding the actual fix: a
>   hand-written nullable-required JSON schema passed directly to
>   `with_structured_output`.
> - **US1 (deploy)**: the three Feature-003 manual steps (Supabase Storage
>   bucket, Railway, Vercel) are now all confirmed working by the project
>   owner — Railway had a real issue (container booted cleanly every time,
>   then got stopped a few seconds later, no traceback) that turned out to
>   be a dashboard-side health-check/service-type config, not a code issue
>   (`psycopg[binary]` and the deploy port were both ruled out during
>   troubleshooting). **The live backend is still running pre-005 code** —
>   validating this feature's actual changes live (the cache, the
>   guardrail, LiteLLM routing, the new `/health`) needs a redeploy after
>   this branch merges, not before.
> - Also added, beyond the original plan: `GET /health` now actually checks
>   Postgres + Qdrant reachability (`503` naming the failed dependency)
>   instead of always returning a static `200 ok` — a `/speckit.analyze`
>   finding against the spec's own Edge Case, not in the original task list.
> - **Test isolation gap found and fixed**: once `/suggest` caches by
>   default, any integration test hitting it for the same seeded user
>   became implicitly subject to that cache — a file-local Redis-flush
>   fixture wasn't enough (a *different* test file reading a *different*
>   test's cached result caused a real, reproducible cross-file failure).
>   Fixed with a global autouse fixture in `tests/conftest.py`, the same
>   pattern as `db_session`'s rollback isolation but for Redis.
> - **One known, unresolved intermittent test failure**:
>   `test_closet_edit_invalidates_the_cache` failed twice across this
>   session's ~275-test full-suite runs, but passed in 6 separate narrower
>   reproductions (3x isolation, paired with its preceding test, an
>   18-test combined-file rerun, a manual script) — the underlying
>   fingerprint/cache mechanism is verified correct; documented in the test
>   itself as full-suite-only and not yet root-caused (leading hypothesis:
>   Supabase pooler contention under this session's own concurrent
>   activity, not a logic bug). Worth a clean look if it recurs.
> - Full no-regression gate: `retrieval_recall` byte-identical to the
>   archived baseline (T013); ruff clean on every file this feature
>   touches. `tasks.md`: 24/25 tasks done — only T008 (live-URL validation)
>   remains, blocked on the pending redeploy above.

## Step 7: Feature 007, ai-improvements

A cert-challenge handoff (not planner-originated) — pasted directly into a fresh worker session as
three build tasks (A/B/C) with acceptance criteria already decided. Full spec-kit cycle run anyway on
branch `007-AI-improvements` (the handoff was decision-complete enough that `/speckit.clarify` needed no
questions — `spec.md`'s checklist passed 16/16 on the first pass), since CLAUDE.md requires it for all
feature work regardless of how the work originated. `/speckit.analyze` found 2 MEDIUM findings (plan.md's
file tree missing two new test files; a new test directory missing its `__init__.py`), both fixed before
implementing.

**What Feature 007 does** (closes two cert rubric gaps plus a real bug, all independent, all in
`backend/`, no frontend/API-contract changes):
- **US1 (L1 semantic sub-layer, P1)**: `retrieve_l1()` (`retrieval/hybrid.py`) already had access to a
  fully embedded pool of long-form section chunks (Wikipedia color theory/harmony/complementary-colors,
  the Chevreul and Munsell PD books — `chunker: section` in `data/kb/manifest.yaml`, embedded by
  `build_kb.py` all along) that retrieval simply never queried; it only ever loaded the small
  hand-written atomic card set. Added a `similarity_search` branch (`_l1_semantic_filter()`, filtering
  `layer==L1 AND granularity==section`) unioned with the existing load-all — genuinely new retrieval
  behavior over data that was already there, zero new ingestion/chunking/embedding code. One real gap
  found reading the existing `build_vectorstore()`: the compound filter needs a payload index on
  `metadata.granularity`, not just the pre-existing `metadata.layer` one (same failure mode
  `build_kb.py`'s own comment already documents for `layer` alone) — added.
- **US2 (live Tavily L3, P2)**: `retrieve_l3()` used to run `kb.vectorstore.similarity_search` against a
  static, pre-ingested `l3_trend_cards.jsonl` collection. It now calls the project's own already-existing
  `external/trends.search_trends()` (a working Tavily wrapper previously only used by an offline
  distillation script) live, at request time, mapping each result into a citable `Document` with a
  synthetic `rule_id` derived from the result's URL. Degrades to `[]` on any exception, mirroring
  `context_assembler`'s weather-lookup fallback pattern. **Deliberately left the static
  `l3_trend_cards.jsonl` ingested in the manifest, unchanged** — `baseline.retrieve()` queries the whole
  Qdrant collection directly and never calls `retrieve_l3`, so removing that source would have silently
  shrunk baseline's corpus, violating the explicit "don't change what baseline returns" constraint;
  `retrieve_l3`'s old static-search code path is what's retired, not the underlying data. Golden set
  fallout: 3 cases (`g12`, `g16`, `g23`) pinned a specific static L3 `rule_id` as "relevant" for
  `retrieval_recall` — a live search can never reproduce a fixed id by construction, so those 3 cases'
  `relevant_rule_ids` were trimmed to their L4/L1 expectations only (commented inline in
  `data/golden_set.yaml`), an intentional, documented test-data update, not a silent regression.
- **US3 (warmth-floor fix, P1)**: the "warmer" refinement's existing bug (documented back in Feature 002
  Phase 4 and again in this handoff) — a flat, absolute warmth floor silently excluded nearly all
  footwear/accessories in this closet — had already been "fixed" with a blanket exemption
  (`_WARMTH_FLOOR_EXEMPT_GROUPS`, footwear/accessory fully skip any floor at all). This feature replaces
  that exemption with the more literal fix: `_category_warmth_ceiling()` computes each category's own
  max achievable warmth from the actual closet, and the floor scales proportionally to that ceiling
  (against the schema's fixed 0-5 range) instead of either a flat absolute number or a full pass-through
  — capped at the ceiling itself so a category's own warmest item always still qualifies, no matter how
  many "warmer" turns accumulate. A zero-ceiling category (e.g. a closet with literally no warmth
  variation in accessories) still degenerates correctly to "never gates," but now as the natural output
  of one formula instead of a hardcoded group list.

**What's verified vs. not — read this before merging.** This session ran in a fresh remote sandbox
clone, not an existing checkout or a `git worktree add` off one. It had **zero `.env` credentials** and
**none of the gitignored `backend/data/` source files** the KB build needs (`data/wikipedia/*.md`,
`data/books/*.epub`, `data/fixtures/wardrobe.json` — only `golden_set.yaml`, `manifest.yaml`, and the 3
`kb/*.jsonl` card files are actually tracked in git). This is the same class of gap the "Gotchas" section
below already documents for a fresh `git worktree add`; it just showed up in a fresh container clone
instead this time. Confirmed two independent ways: `get_kb()` fails on a missing `.epub` before ever
reaching a network call, and the new warmth-floor evidence script fails on `psycopg` connection-string
parsing against a placeholder `DATABASE_URL` before reaching the graph at all.
- **Fully verified this session**: all three tasks' actual logic, via 38 new/updated unit tests
  (`tests/unit/retrieval/test_hybrid.py`, `test_advanced.py` — both new files — plus updates to
  `tests/unit/pipeline/test_graph.py`) that mock the KB/Tavily/DB boundary and exercise the real pure
  functions. The full pre-existing `tests/unit/` suite: 193/193 passing (the only errors, 33, are in
  pre-existing, untouched `test_crud.py`/`test_seed.py`, which need a live DB connection — an
  environment gap, not a regression). `ruff check`/`format` clean on every file this feature touches.
- **NOT verified this session, and this is the real gap**: the eval no-regression gate
  (`eval/harness.py` across all three strategies — the constitution's mandatory check for any
  retrieval-touching change), any integration test hitting the real `/suggest` endpoint
  (`tests/integration/test_suggest_refinement.py`), a live Tavily call actually happening, a LangSmith
  trace confirming it as its own visible step, and — the one the original handoff most wanted —
  **before/after fallback-rate evidence for the warmth-floor fix**. The evidence script
  (`backend/scripts/warmth_floor_evidence.py`) is written and confirmed structurally correct (fails only
  at the DB-connection step, not from a code bug), but neither a "before" nor "after" number was
  captured — the fix (US3's code) was necessarily implemented in the same credential-less session the
  script had to be written in, so the research plan's "one and only chance to get a real baseline
  number" was missed here. A future session should decide whether to revert US3 temporarily to capture a
  true "before," or accept an after-only capture and lean on the unit tests' worked examples instead.
- **The single most important next step before merging this branch**: run
  `uv run python -m whattowear.eval.harness` (all three strategies) in a session with real credentials
  and a full `backend/data/`, and confirm `baseline`'s `retrieval_recall` is byte-identical to the
  archived run while `hybrid`/`advanced` deltas are limited to the 3 intentionally-edited golden cases
  plus any genuine L1-recall improvement. Full task-by-task status, including which of the 35 tasks are
  done vs. blocked and why: `specs/007-ai-improvements/tasks.md`'s environment note near the top.

## The rule that matters most

Never skip /speckit.analyze, and read it like a critic.

Spec Kit's planner over-builds. On a codebase this size it will propose repository
patterns, service layers, and abstract base classes over working code. Every time it
does, point at the constitution's simplicity clause and principle 1, and make it
strip the abstraction out.

This is a solo project. If there is only one concrete implementation today, there is
no interface.

## Running alongside: the milestone writeup

Keep the local, untracked writeup doc (mirrors `docs/mvp-milestone.md`'s
required sections) and fill each section as the matching feature lands, not
at the end.

| Section | Filled in after |
|---|---|
| Problem and audience | now |
| Proposed solution | now |
| Deal with data | 001, 003 |
| Build and deploy agent to API, run in a browser | 003 (minimal), 005 (hardened) |
| E2E prototype, public endpoint | 003 |
| Golden test data set | exists, document it |
| Assess performance | exists, document it |
| Improvements | from judge vs scorer disagreements; also from this feature's `/recommend`-not-`/suggest` trade-off (§Step 4) |

## Appendix: constitution text

Paste into /speckit.constitution.

    Project: What to Wear, an AI personal styling agent. Solo developer. Course
    capstone that may become a product.

    PRINCIPLES

    1. Existing pipeline is authoritative. The retrieval strategies, chunking,
       ingest, KB, and eval harness in backend/src/whattowear are working and
       already evaluated. New features integrate with them. Rewriting them requires
       explicit justification and a passing eval run showing no regression against
       backend/artifacts/eval_runs.

    2. Deterministic core, LLM at the edges. Outfit generation and scoring are pure
       Python and unit-testable. The LLM parses intent and writes rationale. The LLM
       never selects clothing items directly.

    3. Style knowledge gates wardrobe retrieval. The style KB is queried first and
       returns structured directives. Those directives shape the wardrobe query.
       They are never parallel tracks, and structured directives are never passed
       downstream as raw prose.

    4. Grounded output only. Every item in a suggested outfit must exist in the
       user's closet or the shared catalog. Every rationale must cite retrieved
       style principles or scorer output.

    5. Scoring functions are eval metrics. Any function judging outfit quality is
       deterministic code first, then reused in the eval harness. No metric exists
       only inside a prompt.

    6. Schema stability. The item taxonomy already exists in backend/src/whattowear/schema.py
       and categories.py and is frozen as-is: category groups (top, bottom, full_body,
       outerwear, footwear, accessory), the six-value formality enum (casual,
       smart_casual, business_casual, semi_formal, formal, black_tie), warmth 0-5,
       seasons, and hex colors. New features conform to this taxonomy; they do not
       introduce a parallel numeric formality scale or rename existing groups.
       Changes require an explicit migration and are breaking.

    7. Single source of truth for contracts. Pydantic models in backend define the
       API. The frontend consumes generated types from OpenAPI. No hand-maintained
       duplicate types.

    TECHNOLOGY CONSTRAINTS

    - Python 3.12, uv, FastAPI, LangGraph
    - Postgres, auth, and image storage via Supabase (pooler connection, port 6543)
    - Vector search via Qdrant, hybrid dense plus metadata filtering
    - Redis and backend deployment on Railway
    - LangSmith tracing on every LLM and retrieval call
    - Frontend is Next.js on Vercel, built only after design is finalized
    - Backend code lives in backend/, frontend in frontend/. Do not restructure.

    QUALITY BAR

    - Deterministic logic requires unit tests.
    - LLM-dependent paths require an entry in data/golden_set.yaml.
    - Retrieval is inspected before generation is trusted.
    - Simplicity over abstraction. This is a solo project. No repository patterns,
      service layers, or abstract base classes unless there are two concrete
      implementations today.
      