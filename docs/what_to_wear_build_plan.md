# What to Wear: Build Plan

> ⚠️ **SUPERSEDED (2026-07-15). Historical reference only — do not follow the
> taxonomy, file paths, data model, or auth described below.**
>
> This was the initial pre-constitution brainstorm. The authoritative sources
> are now:
> - **Plan / feature roadmap:** `docs/SDD-HANDOFF.md`
> - **Frozen taxonomy + architecture rules:** `.specify/memory/constitution.md`
> - **Shipped feature specs:** `specs/` (e.g. `specs/001-closet-persistence/`)
>
> Known ways this doc is now wrong: it uses the old taxonomy (`one_piece/outer/
> shoes` slots, formality **1–5**) that the constitution overrode (`full_body/
> outerwear/footwear`, six-value formality enum, warmth **0–5**); `backend/app/…`
> paths (real code is `backend/src/whattowear/…`); a local `users` table
> (Feature 001 deliberately has none — `user_id` comes from the JWT); and
> service-key auth (corrected to local ES256/JWKS verification). The design
> *thinking* here — scoring breakdown, golden-set structure, substitution logic —
> is still useful reference for Feature 002; the specifics are not.

Solo dev, one repo, cert challenge scope.

**Stack decisions (locked):**
- Repo: single monorepo, separate from `AIE10`
- Postgres + Auth + Image storage: Supabase
- Vectors: Qdrant (keep, do not migrate to pgvector)
- Backend + Redis: Railway
- Frontend: Vercel (later, after design)
- Orchestration: LangGraph
- Tracing: LangSmith

**Infra reality check:** three providers (Supabase, Railway, Qdrant Cloud). That is the cost of using Supabase. Accepted.

---

## Phase 0: Foundation

Goal: repo exists, services are reachable, nothing is built yet.

### Step 0.1 Create the repo
```bash
gh repo create what-to-wear --private --clone
cd what-to-wear
```

Create the skeleton:
```
backend/  frontend/  data/  docs/  .github/workflows/
```

Add `README.md`, `CLAUDE.md`, `.env.example`, `.gitignore`, `docker-compose.yml`.

### Step 0.2 Backend project init
```bash
cd backend
uv init
uv add fastapi uvicorn[standard] pydantic pydantic-settings \
       sqlalchemy alembic psycopg[binary] \
       langgraph langchain langchain-openai langsmith \
       qdrant-client httpx python-dotenv
uv add --dev pytest ruff
```

### Step 0.3 Provision services
1. **Supabase**: create project. Copy the **pooler** connection string (port 6543), the anon key, and the service role key.
2. **Qdrant Cloud**: create a free cluster. Copy URL + API key.
3. **Railway**: create project, add a Redis service. Copy the Redis URL.
4. **LangSmith**: create a project named `what-to-wear`.

### Step 0.4 Config
Create `backend/app/config.py` with a Pydantic `Settings` class reading:
```
DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_KEY,
QDRANT_URL, QDRANT_API_KEY,
REDIS_URL,
OPENAI_API_KEY, LANGSMITH_API_KEY, LANGSMITH_PROJECT,
WEATHER_API_KEY, TAVILY_API_KEY
```

**Done when:** a script connects to Postgres, Qdrant, and Redis and prints OK for all three.

---

## Phase 1: The schema (blocks everything, do not skip ahead)

Goal: the item taxonomy is frozen. Retrofitting this later is the single most expensive mistake available to you.

### Step 1.1 Decide the taxonomy
Write it in `docs/taxonomy.md` before writing any code.

- **Slots:** `top`, `bottom`, `one_piece`, `outer`, `shoes`, `accessory`
- **Categories per slot:** e.g. top -> t-shirt, shirt, blouse, sweater, hoodie, tank
- **Formality scale:** integer 1 to 5 (1 = loungewear, 5 = black tie)
- **Warmth rating:** integer 1 to 5
- **Seasons:** multi-value from spring, summer, autumn, winter
- **Colors:** list of `{hex, name}`

Accessories are in scope from day one. Your Notion note is right that retrofitting them is costly.

### Step 1.2 SQLAlchemy models
`backend/app/models/db.py`:

- `users` (id, email, created_at)
- `body_profiles` (user_id, body_shape enum, height_cm, skin_tone, hair_color)
- `closet_items` (id, user_id, image_url, slot, category, colors JSONB, fabric, warmth 1-5, formality 1-5, seasons, source enum `upload`/`catalog`, created_at)
- `catalog_items` (same shape, no user_id)
- `outfits` (id, user_id, item_ids JSONB, occasion, rationale, scores JSONB, created_at)
- `feedback` (id, outfit_id, verdict enum `love`/`ok`/`reject`, reason_tags, note, created_at)
- `preference_profiles` (user_id, derived JSONB, updated_at)

### Step 1.3 Pydantic schemas
`backend/app/models/schemas.py`. These are the API contract. Every field the frontend will ever see is defined here and nowhere else.

### Step 1.4 Migrations
```bash
uv run alembic init alembic
uv run alembic revision --autogenerate -m "initial schema"
uv run alembic upgrade head
```

**Done when:** tables exist in Supabase and you can see them in the table editor.

---

## Phase 2: Retrieval layers

Goal: your existing RAG work is behind a clean interface the agent can call.

### Step 2.1 Style KB retriever
Port your existing style RAG into `backend/app/retrieval/style_kb.py`.

Interface:
```python
def retrieve_style_directives(
    occasion: str, season: str, mood: str | None, body_shape: str | None
) -> StyleDirectives
```

`StyleDirectives` is a structured object, not raw text:
```python
class StyleDirectives(BaseModel):
    formality_target: int          # 1-5
    color_guidance: list[str]      # e.g. "neutral base, one accent"
    silhouette_notes: list[str]
    fabric_notes: list[str]
    aesthetic_tags: list[str]
    source_chunks: list[str]       # for grounding + eval
```

This structured output is what shapes the wardrobe query. Do not pass a blob of prose downstream.

### Step 2.2 Wardrobe retriever
`backend/app/retrieval/wardrobe.py`. Qdrant collection `closet_items`.

- Vector: embedding of a synthesized item description
- Payload: user_id, slot, category, colors, warmth, formality, seasons

Interface:
```python
def retrieve_candidates(
    user_id: str, slot: str, filters: WardrobeFilters, k: int = 10
) -> list[ClosetItem]
```

Hard filters go in Qdrant's filter clause (user_id, slot, season, warmth range, formality band). Dense similarity ranks within the filtered set. This is the hybrid you need for the advanced retrieval requirement.

### Step 2.3 Write-through sync
Any insert or update to `closet_items` embeds and upserts to Qdrant in the same code path. No nightly batch job.

**Done when:** a test seeds 30 items, calls `retrieve_candidates` for `slot=top, season=winter`, and gets sensible results back.

---

## Phase 3: Scoring functions (pure Python, no LLM)

Goal: deterministic outfit quality. These double as your eval metrics, which is why they come before evals.

`backend/app/scoring/`:

- `color_harmony(items) -> float` : convert hex to HSL, detect complementary / analogous / neutral-anchored, penalize more than one loud accent
- `formality_coherence(items, target) -> float` : penalize variance across items and distance from target
- `weather_fitness(items, forecast) -> float` : sum warmth vs temperature band, penalize both under and over
- `silhouette_balance(items, body_shape) -> float` : proportion rules pulled from your style KB
- `composite_score(items, context) -> OutfitScore` : weighted sum, returns per-dimension breakdown

Every function returns 0.0 to 1.0 and a short reason string. The reason strings become your rationale text.

**Done when:** unit tests cover an obviously good outfit, an obviously bad one, and one edge case per function.

---

## Phase 4: The outfit engine

Goal: generate candidate outfits without an LLM.

`backend/app/engine/generator.py`:

1. Determine required slots from directives (a wedding needs shoes, a beach day does not need outer)
2. Retrieve top-k candidates per slot (k = 8 is plenty)
3. Prune with hard constraints before combining: warmth vs temperature, formality band, season
4. Generate combinations from the pruned sets, cap total at a few hundred
5. Score every combination with `composite_score`
6. Return top N (N = 3 to 5)

Never brute-force the raw closet. Prune, then combine.

### Substitution
If a required slot has zero candidates after pruning, pull the nearest neighbour from `catalog_items` and mark it as `source=catalog` in the response so the UI can say "you don't own this, but it would work."

**Done when:** given a seeded closet, a request, and a forecast, the engine returns 3 scored outfits in under a second.

---

## Phase 5: The agent graph

Goal: LangGraph orchestrates everything above.

`backend/app/agent/state.py`:
```python
class AgentState(TypedDict):
    user_id: str
    raw_request: str
    intent: RequestIntent | None        # occasion, mood, constraints
    weather: Forecast | None
    profile: BodyProfile | None
    preferences: PreferenceProfile | None
    directives: StyleDirectives | None
    filters: WardrobeFilters | None
    candidates: dict[str, list[ClosetItem]]
    outfits: list[ScoredOutfit]
    rationale: str | None
    messages: list                       # short-term memory
```

`backend/app/agent/graph.py`, nodes in this order:

1. `parse_request` : LLM with structured output -> `RequestIntent`
2. `gather_context` : parallel, weather tool + profile + preference profile
3. `style_retrieval` : style KB -> `StyleDirectives`
4. `build_query` : directives + context -> `WardrobeFilters` (deterministic, no LLM)
5. `wardrobe_retrieval` : per-slot candidates
6. `generate_outfits` : the engine from Phase 4
7. `explain` : LLM writes rationale, grounded strictly in `directives.source_chunks` and the scorer reason strings

Style retrieval **gates** wardrobe retrieval. They are not parallel. This is the core of your architecture and it is what makes the rationale defensible.

### Tools
`backend/app/agent/tools/`: `weather.py` (cached 1h by lat/lon/date), `trends.py` (Tavily, circuit breaker, it fails often).

### Checkpointer
Postgres checkpointer against Supabase, thread_id = conversation id. This gives you short-term memory ("no, something warmer") for free.

**Done when:** you can run the graph from a script with a plain-English request and get outfits plus a rationale, with the full trace visible in LangSmith.

---

## Phase 6: Evals

Goal: numbers you can put in the cert writeup.

### Step 6.1 Golden set
`backend/evals/golden_set.json`, 30 to 50 entries:
```json
{
  "id": "g001",
  "wardrobe_snapshot": "seed_closet_a",
  "request": "something for a winter job interview",
  "weather": {"temp_c": 3, "condition": "rain"},
  "expected": {
    "formality_min": 4,
    "must_include_slots": ["top", "bottom", "outer", "shoes"],
    "warmth_min": 3,
    "forbidden_categories": ["tank", "shorts"]
  }
}
```
Assert on **properties**, not exact item IDs. Item-ID assertions break the moment you touch the seed data.

### Step 6.2 Retrieval evals
- Style KB: Ragas context precision and recall
- Wardrobe: recall at k of items that appear in any acceptable outfit

### Step 6.3 Outfit quality
- Deterministic baseline: your `composite_score`
- LLM judge with a rubric taken directly from the style KB
- Report agreement between the two. Where they disagree is your improvements section.

### Step 6.4 Harness
`backend/evals/run_eval.py`, wraps everything in `ls.tracing_context(enabled=True, project_name=...)` as an explicit context manager. Do not rely on the `LANGSMITH_TRACING` env var, and watch for contextvar propagation breaking across threads.

**Done when:** `uv run python evals/run_eval.py` prints a metrics table and the run appears in LangSmith.

---

## Phase 7: The API

Goal: everything above is reachable over HTTP.

`backend/app/api/`:
```
POST   /auth/*                  (Supabase handles this, backend just verifies JWT)
GET    /closet/items
POST   /closet/items            (upload or catalog pick)
PATCH  /closet/items/{id}
DELETE /closet/items/{id}
POST   /catalog/search
POST   /suggest                 (SSE stream)
POST   /suggest/{id}/regenerate
POST   /outfits/{id}/feedback
GET    /profile
PUT    /profile
```

**Make `/suggest` stream from the start.** Retrofitting SSE into a sync endpoint is genuinely annoying.

Auth: verify the Supabase JWT in a FastAPI dependency, extract `user_id`. Use the **service key** from the backend. Leave RLS off for now, it will silently return empty results and cost you an hour of debugging for zero benefit while you are the only user.

**Done when:** `/docs` renders and you can drive a full suggest-then-feedback loop from Swagger.

---

## Phase 8: Ingestion

Goal: real closets, not just seeds.

1. `POST /closet/items` with an image -> upload to Supabase Storage -> return item id with `status=processing`
2. Background task: VLM call -> extract slot, category, colors (hex), fabric, warmth, formality, seasons -> update row -> embed -> upsert to Qdrant
3. Idempotency key on upload so retries do not duplicate vectors
4. `PATCH` lets the user correct any extracted field. The VLM will get fabric wrong and that is fine.

Skip AI segmentation of full-body photos. Its own strategic note flags it as technically complex, and it earns nothing on the rubric.

### Catalog seed
Build `catalog_items` from a licensed source. Same taxonomy, same embedding pipeline. This gives you cold start, substitution targets, and a stable eval wardrobe in one artifact.

**Done when:** you upload a photo of a real shirt and it appears in your closet with plausible metadata.

---

## Phase 9: Memory

Goal: the system learns from feedback. This is a graded requirement.

1. `POST /outfits/{id}/feedback` writes to `feedback`
2. A `derive_preferences` job (run on write, it is cheap) aggregates feedback into `preference_profiles`:
   - rejected colors, rejected categories
   - favored aesthetic tags
   - formality drift (does the user always dress down from the target?)
3. `gather_context` loads the preference profile
4. `parse_request` uses it as prompt context, `composite_score` uses it as a soft re-ranking weight

Short-term memory is already handled by the LangGraph checkpointer from Phase 5.

**Done when:** rejecting three yellow outfits measurably reduces yellow in subsequent suggestions.

---

## Phase 10: Production hardening

1. **LLM gateway**: LiteLLM in front of every model call. One place for routing, retries, fallback model, cost tracking.
2. **Semantic cache**: on style KB retrieval. The same (occasion, season) pair hits constantly. Redis-backed.
3. **Guardrails**:
   - Input: scope check, reject non-styling requests
   - Output: **every returned item_id must exist in the user's closet or catalog.** This is your hallucination killer and the single highest-value guardrail in the system.
4. **Prompt caching**: on the style KB system prompt.

---

## Phase 11: Deploy

1. `uv run langgraph dockerfile Dockerfile` (do not hand-roll it)
2. Railway: deploy `backend/` as a service, Redis alongside it, env vars pointing at Supabase and Qdrant
3. Health check endpoint, verify from outside your network
4. **Wake Supabase before any demo.** Free-tier projects pause after a week of inactivity and you do not want to find that out an hour before Demo Day.

---

## Phase 12: Frontend

Only after design lands.

1. Export OpenAPI: `curl localhost:8000/openapi.json > ../frontend/openapi.json`
2. Generate types: `npx openapi-typescript openapi.json -o src/types/api.ts`
3. Never hand-maintain a second copy of `ClosetItem`. The Pydantic model is the single source of truth.
4. Vercel, root directory set to `frontend/`

---

## Running alongside: the writeup

`docs/cert_challenge.md`. Fill in each section **as you finish the matching phase**, not at the end.

| Section | Filled in after |
|---|---|
| 1. Problem and audience | now |
| 2. Proposed solution | now |
| 3. Deal with data | Phase 2 and 8 |
| 4. Build and deploy agent to API | Phase 7 and 11 |
| 5. E2E prototype | Phase 12 |
| 6. Golden test data set | Phase 6 |
| 7. Assess performance | Phase 6 |
| 8. Improvements | Phase 6, from judge/scorer disagreements |

Writing these from memory at the end is how people lose points on work they actually did.

---

## Critical path, compressed

If time gets tight, this is the minimum that still passes:

**1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 11**

Phases 8, 9, 10, 12 are the ones to cut or shrink, in that order of pain. Note that cutting Phase 9 costs you the memory requirement, so shrink it rather than dropping it: feedback capture plus a simple rejected-colors list is enough to demonstrate the pattern.
