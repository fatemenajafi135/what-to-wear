# What to Wear: Spec-Driven Development Handoff

## Where the project stands

Monorepo. `backend/` holds all Python. `frontend/` is empty — design has
landed (`/design`, committed) and frontend build starts with Feature 003 (see
Step 4). Baseline is committed to `main`. Spec Kit is initialized.

**Already built and working. Do not rewrite:**
- `backend/src/whattowear/retrieval/` : baseline, hybrid, advanced retrievers
- `backend/src/whattowear/ingest/` : loaders, chunkers, KB build, wiki refine
- `backend/src/whattowear/kb.py` : style knowledge base
- `backend/src/whattowear/pipeline/` : query_builder, context_assembler, generator, cite, run
- `backend/src/whattowear/external/` : weather, trends
- `backend/src/whattowear/memory/store.py` : partial
- `backend/src/whattowear/eval/` and `backend/evals/` : Ragas plus LLM judge
- `backend/data/golden_set.yaml`, `backend/artifacts/eval_runs/*.jsonl` : evaluated results
- **Feature 001 (closet-persistence), done**: `backend/src/whattowear/db.py`,
  `models.py`, `crud.py`, `auth.py`, `backend/alembic/` — persistent per-user
  closet + shared catalog in Postgres (Supabase), JWT auth (ES256/JWKS), full
  CRUD (`GET`/`POST`/`POST .../bulk`/`PATCH`/`DELETE` on `/wardrobe/items`,
  `GET /catalog/items`). `context_assembler.load_wardrobe()` reads Postgres
  instead of the JSON fixture, which is now catalog-seed-only. No change to
  retrieval behavior — verified via the eval no-regression gate.

**Not built yet:**
1. LangGraph agent graph. Pipeline is currently a linear run.
2. Deterministic scoring (color harmony, formality coherence, weather fitness, silhouette balance).
3. Combinatorial outfit generation engine.
4. Vision ingestion (photo to item metadata) — **in progress, minimal slice, see Feature 003 below.**
5. Preference memory from feedback.
6. Production hardening and deployment — **the "deploy publicly" slice pulled forward into Feature 003; full hardening (LiteLLM gateway, semantic cache, guardrails) still deferred to 005.**
7. Frontend — **in progress, see Feature 003 below.** `/design` (committed) has an interactive HTML prototype; `docs/design-backend-conflict-report.md` (local, untracked) has the full design↔backend conflict audit that drove Feature 003's scope.

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
| 002 | styling-agent | The big one. Pipeline becomes a graph, plus scoring. **Broadened** to also fold in the recommend-flow cleanup (auth-gate `/recommend`) and unit-test backfill for the deterministic pipeline. Delivered in phases (see Step 3). **Phase 1 ✅ done and merged**; Phases 2–4 paused — deliberately reordered behind Feature 003 (see below), resume after. |
| 003 | **mvp-app** *(redefined — was "closet-ingestion")* | **Next up.** A milestone-driven, minimal, end-to-end vertical slice: sign-in → add-item-by-photo (VLM) → view closet → get suggestions (via the existing `/recommend`, not `/suggest`) → deployed publicly. Absorbs the original 003's core (photo→VLM, narrowed to one item per photo) and a thin slice of 005 (deploy only). See Step 4. |
| 004 | preference-memory | Feedback capture, preference derivation. Unchanged, still after 003. |
| 005 | production-hardening | Gateway, cache, guardrails, **full** deploy hardening (bare deploy pulled into 003; this is everything beyond that). |

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
> Notes. The `/speckit.specify` / `/speckit.plan` prompts below are kept
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

> **`/speckit.specify` + `/speckit.clarify` done.** `spec.md` has 4 required P1
> user stories (sign in, add-by-photo, view closet, get suggestion); quality
> checklist 16/16, zero `[NEEDS CLARIFICATION]` markers (everything was
> already decided in planning before the spec was written). Full narrative:
> `docs/003-mvp-app-planning-report.md` (local, untracked).

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

## Step 5: Features 004 to 005

Same loop each time. Run /speckit.converge before 004, since memory/store.py may
already cover part of it.

- 004 preference-memory: feedback endpoint, derive a preference profile from
  rejections (rejected colors, avoided categories, formality drift), feed into
  parse_request and as a soft re-ranking weight.
- 005 production-hardening: LiteLLM gateway, semantic cache on KB retrieval, output
  guardrail asserting every item_id exists, `uv run langgraph dockerfile Dockerfile`,
  deploy to Railway (beyond the bare deploy already done in 003).

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
      