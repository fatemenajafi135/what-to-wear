# Quickstart: AI layer (feature 007)

Prerequisites: everything in `specs/002-backend-foundation/quickstart.md` (Docker, `uv`,
Node/npm for the pinned Supabase CLI), plus real API credentials for the AI Gateway, Cohere,
Tavily and LangSmith (ask the project owner — this slice costs money to run for real). A
local checkout of the corpus at `../w2w-corpus/` (outside the repo) if you intend to run
ingestion; without it, everything except ingestion and the live eval gate still works.

## One-time setup

```bash
cd infra && npm install                 # pinned Supabase CLI (unchanged from 002)
```

No separate install step for Qdrant — `infra/docker-compose.yml` pins the image.

## Local stack — three things running

```bash
cd infra && npx supabase start          # Postgres, Auth, Storage
cd infra && docker compose up -d        # Qdrant, localhost:6333
cd backend && uv sync && cp .env.example .env   # then fill in the real keys — see below
```

`.env.example`'s AI-layer section lists every variable this feature needs
(`AI_GATEWAY_API_KEY`, `AI_GATEWAY_BASE_URL`, `WTW_CHAT_MODEL`, `WTW_EMBEDDING_MODEL`,
`WTW_JUDGE_MODEL`, `WTW_EMBEDDING_DIMS`, `COHERE_API_KEY`, `WTW_RERANK_MODEL`,
`TAVILY_API_KEY`, `LANGSMITH_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT`,
`WTW_QDRANT_URL`, `CORPUS_LOCAL_DIR`) as placeholders. `WTW_QDRANT_URL`'s placeholder
(`http://localhost:6333`) is already correct for the local container above — nothing to
edit there for a stock local setup.

Verify Qdrant is up:

```bash
curl -s localhost:6333/healthz   # "healthz check passed"
```

## Everything imports with zero environment variables

```bash
env -i python3 -c "import sys; sys.path.insert(0, 'backend/src'); import whattowear.pipeline.graph"
```

Must succeed — this is the regression test feature 002 established, extended to every
AI module this feature adds (`test_import_safety.py`).

## Run the unit tests (no live calls)

```bash
cd backend
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run lint-imports
```

## Build the knowledge-base index (needs `../w2w-corpus/` and a gateway key — real cost)

```bash
cd backend
uv run python -m whattowear.ingest.cli --corpus-dir ../../w2w-corpus
```

Reads `infra/corpus.yaml`, chunks every `ingest: true` source, embeds via the AI Gateway,
and upserts into the local Qdrant collection. Idempotent by content hash — a second run with
no source changes reports "nothing changed" and re-embeds nothing (SC-005). Never reads a
`../w2w-corpus/` path from anywhere except this one `--corpus-dir` (or `$CORPUS_LOCAL_DIR`)
value.

## The eval gate — this feature's actual acceptance bar

```bash
cd backend
uv run python -m whattowear.eval.harness --strategies advanced --approach grounded
uv run python -m whattowear.eval.harness --strategies advanced --approach engine
```

Writes `backend/artifacts/eval_runs/advanced.jsonl` and `advanced-engine.jsonl`. Compare the
printed summary table against `../app-legacy/docs/eval-baselines/010-engine/COMPARISON.md`,
metric by metric — this comparison, not a passing `pytest` run, is what this feature reports
against in its final write-up.

Score with the isolated RAGAS/openevals project (separate environment on purpose — Research §9):

```bash
cd backend/evals
uv sync   # separate lockfile/venv from backend/ itself — do not merge
uv run python score_ragas.py ../artifacts/eval_runs/advanced.jsonl
```

## Proving the two eval projects really are isolated

```bash
cd backend && uv run python -c "import langchain_cohere"        # backend/'s own env — succeeds
cd backend/evals && uv run python -c "import langchain_community; print(langchain_community.__version__)"  # 0.3.31
```

If `backend/`'s own `uv sync` ever pulls in `langchain-community==0.3.31`, the isolation has
broken — that pin belongs only to `backend/evals/pyproject.toml`.
