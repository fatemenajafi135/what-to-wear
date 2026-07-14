"""Single LLM-gateway config layer.

Every model / embedding call in the package is created here, pointed at the
Vercel AI Gateway. This is the graded "one explicit config layer" requirement:
no module constructs a provider SDK client directly.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from langchain_cohere import CohereRerank
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

load_dotenv()


# --- gateway + model config (env-overridable) --------------------------------

GATEWAY_BASE_URL = os.environ.get("AI_GATEWAY_BASE_URL", "https://ai-gateway.vercel.sh/v1")
CHAT_MODEL = os.environ.get("WTW_CHAT_MODEL", "openai/gpt-5.4-mini")
EMBEDDING_MODEL = os.environ.get("WTW_EMBEDDING_MODEL", "openai/text-embedding-3-small")
JUDGE_MODEL = os.environ.get("WTW_JUDGE_MODEL", CHAT_MODEL)
EMBEDDING_DIMS = int(os.environ.get("WTW_EMBEDDING_DIMS", "1536"))
RERANK_MODEL = os.environ.get("WTW_RERANK_MODEL", "rerank-v4.0-fast")


def _require_langsmith() -> None:
    """LangSmith tracing is mandatory, not optional. Fails fast at the point any
    LLM/embedding/rerank call is about to be made — offline imports stay clean."""
    if not os.environ.get("LANGSMITH_API_KEY"):
        raise RuntimeError(
            "LANGSMITH_API_KEY is required — tracing is mandatory in this project. "
            "Set it in .env (see .env.example)."
        )
    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", "whattowear-rag")


def _gateway_key() -> str:
    """Gateway API key, with the course's VERCEL_OIDC_TOKEN fallback."""
    _require_langsmith()
    key = os.environ.get("AI_GATEWAY_API_KEY") or os.environ.get("VERCEL_OIDC_TOKEN")
    if not key:
        raise RuntimeError(
            "No gateway key found. Set AI_GATEWAY_API_KEY (or VERCEL_OIDC_TOKEN) in .env"
        )
    return key


# --- factories ---------------------------------------------------------------


def get_chat_model(model: str | None = None, temperature: float = 0.2, **kwargs) -> ChatOpenAI:
    """A chat model routed through the gateway."""
    return ChatOpenAI(
        model=model or CHAT_MODEL,
        base_url=GATEWAY_BASE_URL,
        api_key=_gateway_key(),
        temperature=temperature,
        **kwargs,
    )


def get_judge_model(**kwargs) -> ChatOpenAI:
    """The LLM-as-judge model (deterministic, temp 0) through the gateway."""
    return get_chat_model(model=JUDGE_MODEL, temperature=0.0, **kwargs)


def get_embeddings(model: str | None = None) -> OpenAIEmbeddings:
    """Embeddings routed through the gateway.

    check_embedding_ctx_length=False: langchain_openai pre-tokenizes input into
    integer token arrays by default (fine for OpenAI's literal API), but the
    gateway proxy rejects that and expects raw text strings — same workaround
    the course uses for its Fireworks-gateway embeddings (AIE10 app/rag.py)."""
    return OpenAIEmbeddings(
        model=model or EMBEDDING_MODEL,
        base_url=GATEWAY_BASE_URL,
        api_key=_gateway_key(),
        check_embedding_ctx_length=False,
    )


def get_reranker(top_n: int = 5) -> CohereRerank:
    """Cohere reranker for the advanced retrieval second stage."""
    _require_langsmith()
    return CohereRerank(
        model=RERANK_MODEL,
        top_n=top_n,
        cohere_api_key=os.environ.get("COHERE_API_KEY"),
    )
