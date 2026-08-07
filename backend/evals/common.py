"""Shared gateway wiring for the isolated evals project.

Everything routes through the Vercel AI Gateway (same as the main
package): one endpoint for the RAGAS judge, the embedding model, and the
openevals LLM judge. This project deliberately never imports from
`whattowear` (specs/007-ai-port/research.md §9's isolation) — its own
env reads via `python-dotenv` are correct here, not a regression of the
main package's `core.config.Settings` consolidation.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

# load the main package's .env (one level up) so keys are shared
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
load_dotenv()

GATEWAY_BASE_URL = os.environ.get("AI_GATEWAY_BASE_URL", "https://ai-gateway.vercel.sh/v1")
JUDGE_MODEL = os.environ.get("WTW_JUDGE_MODEL", "openai/gpt-5.4-mini")
EMBEDDING_MODEL = os.environ.get("WTW_EMBEDDING_MODEL", "openai/text-embedding-3-small")

ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "eval_runs"


def _require_langsmith() -> None:
    """Tracing is mandatory (not optional), mirroring the main package's policy."""
    if not os.environ.get("LANGSMITH_API_KEY"):
        raise RuntimeError("LANGSMITH_API_KEY is required — tracing is mandatory. Set it in ../.env")
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", "whattowear-rag")


def gateway_key() -> str:
    _require_langsmith()
    key = os.environ.get("AI_GATEWAY_API_KEY") or os.environ.get("VERCEL_OIDC_TOKEN")
    if not key:
        raise RuntimeError("Set AI_GATEWAY_API_KEY in ../.env")
    return key


def gateway_openai_client():
    """Async OpenAI client pointed at the gateway, wrapped for LangSmith
    tracing (RAGAS calls this client directly, bypassing LangChain's
    automatic instrumentation, so we wrap it explicitly). Must be
    AsyncOpenAI: RAGAS's collections-API metrics (score_ragas.py) call
    .ascore(), which needs an async-capable client — a sync client raises
    "Cannot use agenerate() with a synchronous client" on every call."""
    import openai
    from langsmith.wrappers import wrap_openai

    client = openai.AsyncOpenAI(base_url=GATEWAY_BASE_URL, api_key=gateway_key())
    return wrap_openai(client)


def ragas_judge_llm():
    import instructor
    from ragas.llms import llm_factory

    return llm_factory(
        JUDGE_MODEL,
        provider="openai",
        client=gateway_openai_client(),
        mode=instructor.Mode.TOOLS,
        max_tokens=4096,
    )


def ragas_embeddings():
    from ragas.embeddings import embedding_factory

    return embedding_factory("openai", model=EMBEDDING_MODEL, client=gateway_openai_client())


def openevals_judge_llm():
    """LangChain ChatOpenAI pointed at the gateway, for openevals judges."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=JUDGE_MODEL, base_url=GATEWAY_BASE_URL, api_key=gateway_key(), temperature=0.0)


def load_runs(strategy: str) -> list[dict]:
    path = ARTIFACTS_DIR / f"{strategy}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — run `python -m whattowear.eval.harness` first")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def discover_strategies() -> list[str]:
    if not ARTIFACTS_DIR.exists():
        return []
    return sorted(p.stem for p in ARTIFACTS_DIR.glob("*.jsonl"))
