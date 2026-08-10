"""LLM/embedding/rerank client factories — the one place a provider SDK
client is constructed (legacy `config.py`'s "single LLM-gateway config
layer" requirement, ported unchanged in substance). Settings themselves
live in `core.config` (data only); this module turns them into the actual
`ChatLiteLLM`/`OpenAIEmbeddings`/`CohereRerank` objects that structurally
satisfy `ports.LLMClient` — split out so `core/config.py` never imports a
LangChain/litellm package (specs/007-ai-port/tasks.md T002).

Every factory is call-time lazy: nothing here runs at import time, so
`import whattowear.adapters.llm_gateway` needs zero environment variables
(constitution Technology Constraints). A missing required key raises only
when a factory that needs it is actually called — same guarantee
`core.config.get_settings()` already gives `DATABASE_URL`.
"""

from __future__ import annotations

import base64
from typing import Any

import litellm
from langchain_cohere import CohereRerank
from langchain_litellm import ChatLiteLLM
from langchain_openai import OpenAIEmbeddings
from pydantic import SecretStr

from ..core.config import get_settings


def _require_langsmith() -> None:
    """LangSmith tracing is mandatory, not optional (constitution Technology
    Constraints) — fails fast at the point any LLM/embedding/rerank call is
    about to be made, never at import."""
    settings = get_settings()
    if not settings.langsmith_api_key:
        raise RuntimeError(
            "LANGSMITH_API_KEY is required — tracing is mandatory in this project. Set it in .env (see .env.example)."
        )
    import os

    os.environ.setdefault("LANGSMITH_TRACING", "true" if settings.langsmith_tracing else "false")
    os.environ.setdefault("LANGSMITH_PROJECT", settings.langsmith_project)


def _gateway_key() -> str:
    """Gateway API key, with the legacy `VERCEL_OIDC_TOKEN` fallback carried
    forward unchanged (research.md §1 — not this port's concern to remove)."""
    _require_langsmith()
    settings = get_settings()
    key = settings.ai_gateway_api_key or settings.vercel_oidc_token
    if not key:
        raise RuntimeError("No gateway key found. Set AI_GATEWAY_API_KEY (or VERCEL_OIDC_TOKEN) in .env")
    return key


def get_chat_model(model: str | None = None, temperature: float = 0.2, **kwargs: Any) -> ChatLiteLLM:
    """A chat model routed through the AI Gateway via litellm — retry on
    transient failure (`max_retries`) and LangSmith-visible cost/usage on
    every call. `max_retries` is litellm's own transient-failure retry
    (timeouts, rate limits, 5xx); non-transient errors are not retried."""
    settings = get_settings()
    return ChatLiteLLM(
        model=model or settings.wtw_chat_model,
        api_base=settings.ai_gateway_base_url,
        api_key=_gateway_key(),
        temperature=temperature,
        max_retries=3,
        **kwargs,
    )


def get_judge_model(**kwargs: Any) -> ChatLiteLLM:
    """The LLM-as-judge model (deterministic, temp 0) through the gateway."""
    return get_chat_model(model=get_settings().judge_model, temperature=0.0, **kwargs)


def get_embeddings(model: str | None = None) -> OpenAIEmbeddings:
    """Embeddings routed through the gateway.

    `check_embedding_ctx_length=False`: `langchain_openai` pre-tokenizes
    input into integer token arrays by default (fine for OpenAI's literal
    API), but the gateway proxy rejects that and expects raw text strings."""
    settings = get_settings()
    return OpenAIEmbeddings(
        model=model or settings.wtw_embedding_model,
        base_url=settings.ai_gateway_base_url,
        api_key=SecretStr(_gateway_key()),
        check_embedding_ctx_length=False,
    )


def edit_image(image_bytes: bytes, mime_type: str, prompt: str) -> bytes:
    """Feature 018's generative isolation strategy (`adapters/
    isolation_generative.py`) — routes through this SAME gateway config
    (`ai_gateway_base_url`/`_gateway_key()`), not a second LLM client.

    No LangChain wrapper class exists for image editing the way
    `ChatLiteLLM` exists for chat (`get_chat_model` above), so this calls
    `litellm.image_edit` directly — `litellm` is already a direct
    dependency (`langchain_litellm` itself depends on it), not a new one.
    Raises on a genuine call failure; the caller
    (`isolation_generative.py`) catches it into a failed `IsolationOutcome`,
    same fail-soft contract every isolation strategy has (`ports.
    IsolationClient`)."""
    settings = get_settings()
    response = litellm.image_edit(
        model=settings.generative_isolation_model,
        image=[(f"photo.{mime_type.split('/')[-1]}", image_bytes, mime_type)],
        prompt=prompt,
        api_base=settings.ai_gateway_base_url,
        api_key=_gateway_key(),
    )
    b64 = response.data[0].b64_json
    if not b64:
        raise RuntimeError("Image edit call returned no image data")
    return base64.b64decode(b64)


def get_reranker(top_n: int = 5) -> CohereRerank:
    """Cohere reranker for the advanced retrieval second stage."""
    _require_langsmith()
    settings = get_settings()
    return CohereRerank(
        model=settings.wtw_rerank_model,
        top_n=top_n,
        cohere_api_key=SecretStr(settings.cohere_api_key) if settings.cohere_api_key else None,
    )
