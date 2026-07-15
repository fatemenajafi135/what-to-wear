# What to Wear: Spec-Driven Development Handoff

## Where the project stands

Monorepo. `backend/` holds all Python. `frontend/` is empty until design lands.
Baseline is committed to `main`. Spec Kit is initialized.

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
4. Vision ingestion (photo to item metadata).
5. Preference memory from feedback.
6. Production hardening and deployment.

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

| # | Feature | Notes |
|---|---|---|
| 001 | closet-persistence | Blocks everything. Fixture becomes a real database. |
| 002 | styling-agent | The big one. Pipeline becomes a graph, plus scoring. |
| 003 | closet-ingestion | Photo to metadata via VLM. No full-body segmentation. |
| 004 | preference-memory | Feedback capture, preference derivation. |
| 005 | production-hardening | Gateway, cache, guardrails, deploy. |

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

## Step 4: Features 003 to 005

Same loop each time. Run /speckit.converge before 004, since memory/store.py may
already cover part of it.

- 003 closet-ingestion: photo to Supabase Storage, VLM extracts metadata into the
  existing schema, user can correct any field, idempotency key on upload. Skip
  full-body segmentation.
- 004 preference-memory: feedback endpoint, derive a preference profile from
  rejections (rejected colors, avoided categories, formality drift), feed into
  parse_request and as a soft re-ranking weight.
- 005 production-hardening: LiteLLM gateway, semantic cache on KB retrieval, output
  guardrail asserting every item_id exists, `uv run langgraph dockerfile Dockerfile`,
  deploy to Railway.

## The rule that matters most

Never skip /speckit.analyze, and read it like a critic.

Spec Kit's planner over-builds. On a codebase this size it will propose repository
patterns, service layers, and abstract base classes over working code. Every time it
does, point at the constitution's simplicity clause and principle 1, and make it
strip the abstraction out.

This is a solo project. If there is only one concrete implementation today, there is
no interface.

## Running alongside: the cert writeup

Keep docs/cert_challenge.md and fill each section as the matching feature lands,
not at the end.

| Section | Filled in after |
|---|---|
| Problem and audience | now |
| Proposed solution | now |
| Deal with data | 001, 003 |
| Build and deploy agent to API | 002, 005 |
| E2E prototype | frontend |
| Golden test data set | exists, document it |
| Assess performance | exists, document it |
| Improvements | from judge vs scorer disagreements |

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
      