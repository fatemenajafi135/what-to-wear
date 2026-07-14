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
cp .env.example .env      # fill AI_GATEWAY_API_KEY, TAVILY_API_KEY, COHERE_API_KEY
uv sync
```

All model/embedding calls route through the **Vercel AI Gateway** (`config.py`) —
the single gateway layer, no direct provider SDK calls.

## Run

```bash
# 1. Build the knowledge base (embeds via gateway; Wikipedia fetched + cached)
uv run python -m whattowear.ingest.build_kb --embed

# 2. Get a recommendation from the entrypoint
uv run python -c "from whattowear.pipeline.run import recommend; \
  from whattowear.pipeline.cite import render_text; \
  print(render_text(recommend('wedding', mood='elegant', temp_c=12)))"

# 3. Or run the thin test API (no UI)
uv run uvicorn whattowear.api:app --reload
#    POST /recommend {"occasion":"office","temp_c":8,"strategy":"advanced"}

# 4. Eval harness — run the pipeline over the golden set, write artifacts
uv run python -m whattowear.eval.harness            # baseline vs hybrid vs advanced

# 5. Score the artifacts (isolated venv — avoids the RAGAS dependency conflict)
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
src/whattowear/   ingest/ retrieval/ pipeline/ memory/ external/ eval/  + config, schema, kb, api
data/             kb/ (manifest + distilled cards + cache)  fixtures/  golden_set.yaml
evals/            isolated uv project: RAGAS + openevals scoring of run artifacts
notebooks/        01 chunking · 02 retrieval comparison · 03 evals + conclusions
```
