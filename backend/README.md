# What to Wear — RAG styling engine

Grounded-assembly RAG: given a user's **wardrobe** + a **context** (occasion,
mood, weather), it assembles an outfit **from items they already own**, obeying
rules retrieved from a fashion knowledge base, and **cites the rules**. Built as
the cert-challenge deliverable *and* the product's recommendation engine (see
`../plan` / the handoff docs).

> This is a **grounded-assembly** task, not Q&A: we don't retrieve "the answer",
> we retrieve the *rules the answer must obey*, then construct the outfit from
> inventory and cite the rules.

## Architecture (5-stage deterministic pipeline)

```
context assembler → query builder + router → retriever (hybrid) → grounded generator → cited output
```

Four knowledge layers, each with one role — **Filter → Combine → Elevate → Personalize**:

| Layer | Role | Retrieval method |
|---|---|---|
| **L4** Occasion+Weather | Filter (eligibility) | structured metadata lookup |
| **L1** Static harmony | Combine (what goes together) | load-all atomic rules |
| **L3** Trendy | Elevate (what's current) | dense vector + Cohere rerank |
| **L2** Seasonal color | Personalize | **gated — never wired** (no user coloring yet) |

## Setup

```bash
cp .env.example .env      # fill the gateway keys AND the database vars (below)
uv sync --group dev       # --group dev adds pytest + ruff
```

`.env` needs:
- **Gateway / retrieval:** `AI_GATEWAY_API_KEY`, `TAVILY_API_KEY`,
  `COHERE_API_KEY`, `WTW_QDRANT_URL` (+ `WTW_QDRANT_API_KEY`)
- **Database + auth (Feature 001):** `DATABASE_URL` (Supabase pooler, port 6543)
  and `SUPABASE_URL` (for JWT/JWKS verification). The app raises on startup
  without `DATABASE_URL`. Optionally `DATABASE_URL_DIRECT` (port 5432) for
  running migrations off the pooler.

All model/embedding calls route through the **Vercel AI Gateway** (`config.py`) —
the single gateway layer, no direct provider SDK calls.

### Database (Feature 001: closet persistence)

The wardrobe is now a **per-user Postgres closet** (Supabase), not a JSON
fixture. Apply migrations and seed the shared catalog + eval-baseline user once:

```bash
uv run alembic upgrade head                            # create tables
uv run python -m whattowear.crud seed-catalog          # 40 catalog items from the fixture
uv run python -m whattowear.crud seed-eval-baseline    # eval baseline user's closet (no-regression gate)
```

See `../specs/001-closet-persistence/` for the full spec/plan/quickstart, and
`../docs/SDD-HANDOFF.md` for where the project is headed next (Feature 002).

## Run

```bash
# 1. Build the knowledge base (embeds via gateway; Wikipedia fetched + cached)
uv run python -m whattowear.ingest.build_kb --embed

# 2. Get a recommendation from the entrypoint
uv run python -c "from whattowear.pipeline.run import recommend; \
  from whattowear.pipeline.cite import render_text; \
  print(render_text(recommend('wedding', mood='elegant', temp_c=12)))"

# 3. Or run the API (Swagger UI at /docs)
uv run uvicorn whattowear.api:app --reload
#    Closet CRUD (JWT-auth'd, Feature 001):
#      GET/POST /wardrobe/items · POST /wardrobe/items/bulk · PATCH/DELETE /wardrobe/items/{id}
#      GET /catalog/items
#    POST /recommend {"occasion":"office","temp_c":8,"strategy":"advanced"}
#      ⚠️ /recommend is currently UNAUTHENTICATED (known gap, fixed in Feature 002 Phase 1)

# 4. Run the tests (unit + integration; hit the real Supabase DB via a
#    rolled-back-transaction fixture — need DB creds + network)
uv run pytest tests/ -q

# 5. Eval harness — run the pipeline over the golden set, write artifacts.
#    Makes many external calls; flaky under transient network drops. Compare
#    retrieval_recall across runs (deterministic); generation checks drift from
#    LLM sampling, not a regression.
uv run python -m whattowear.eval.harness            # baseline vs hybrid vs advanced

# 6. Score the artifacts (isolated venv — avoids the RAGAS dependency conflict)
cd evals && uv sync && uv run python score_ragas.py && uv run python judge.py
```

## Graded-artifact index

| Requirement | Where |
|---|---|
| LLM gateway (single config layer) | `src/whattowear/config.py` |
| Memory component | `src/whattowear/memory/store.py` (short-term `InMemorySaver` + long-term `InMemoryStore`) |
| Chunking strategy + justification | `notebooks/01_ingest_and_chunking.ipynb`, `src/whattowear/ingest/chunkers.py` |
| Own personal data (RAG) | `data/kb/` + `manifest.yaml` (ingested KB) |
| External APIs / agentic search | `src/whattowear/external/weather.py` (Open-Meteo), `external/trends.py` (Tavily) |
| User questions | `questions.md` |
| Advanced retrieval + baseline→advanced table | `notebooks/02_retrieval_baseline_vs_advanced.ipynb`, `retrieval/` |
| Change-one-variable experiment | `notebooks/02` (chunk-size sweep) |
| Golden test set (outfit properties) | `data/golden_set.yaml` |
| Two-part eval harness + conclusions | `notebooks/03_eval_harness_and_conclusions.ipynb`, `eval/`, `evals/` |
| Citations / grounding proof | `src/whattowear/pipeline/cite.py` |
| Attributions (CC-BY-SA) | `ATTRIBUTIONS.md` (generated) |

## Layout

```
src/whattowear/   ingest/ retrieval/ pipeline/ memory/ external/ eval/
                  config, schema, kb, api                        (RAG engine)
                  db, models, crud, auth                         (persistence + auth, Feature 001)
alembic/          migrations (0001_initial_wardrobe_schema)
tests/            unit/ + integration/ (pytest; run against the live DB)
data/             kb/ (manifest + distilled cards + cache)  fixtures/  golden_set.yaml
evals/            isolated uv project: RAGAS + openevals scoring of run artifacts
notebooks/        01 chunking · 02 retrieval comparison · 03 evals + conclusions
```
