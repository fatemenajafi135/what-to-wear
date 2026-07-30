"""Application settings, loaded from the environment on first use.

`get_settings()` is the only way to read configuration. There is no
module-level `Settings()` instance: constructing one eagerly would make
`import whattowear` require `DATABASE_URL` to be set, reproducing the legacy
`db.py` defect this package exists to avoid (see
specs/002-backend-foundation/research.md §1). `lru_cache` gives the
"construct once, reuse" behaviour a module-level singleton would have,
without paying for it at import time.

Feature 007 (AI layer port) extends this with every AI-layer setting,
consolidating what the legacy `config.py`/`db.py`/`build_kb.py` each read via
their own independent `load_dotenv()` + `os.environ.get()` call into the one
config layer this module's own docstring always aspired to be (research.md
§10). All AI fields are optional here — a missing key must not block
`get_settings()` for a caller that only needs `database_url`; each adapter
that actually needs a key (`adapters/llm_gateway.py`) raises its own clear
error at the point of use, mirroring the legacy `_gateway_key()`/
`_require_langsmith()` pattern exactly, just sourced from `Settings` instead
of `os.environ` directly.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # Direct connection (session mode, port 5432), preferred by LangGraph's
    # PostgresSaver checkpointer over the transaction-mode pooler (feature
    # 007's memory/store.py) — optional escape hatch, not required for the
    # app to boot.
    database_url_direct: str | None = None
    log_level: str = "INFO"
    environment: str = "development"
    supabase_url: str
    supabase_jwt_aud: str = "authenticated"

    # --- AI Gateway (Vercel AI Gateway) — every LLM/embedding call ------------
    ai_gateway_api_key: str | None = None
    ai_gateway_base_url: str = "https://ai-gateway.vercel.sh/v1"
    # Course-precedent fallback for the gateway key (legacy config.py) —
    # carried forward unchanged, not this port's concern to remove.
    vercel_oidc_token: str | None = None

    wtw_chat_model: str = "openai/gpt-5.4-mini"
    wtw_embedding_model: str = "openai/text-embedding-3-small"
    wtw_judge_model: str | None = None  # defaults to wtw_chat_model if unset
    wtw_vision_model: str | None = None  # defaults to wtw_chat_model if unset (vision.py)
    wtw_embedding_dims: int = 1536

    # --- Cohere rerank (L3 only, retrieval/advanced.py) -----------------------
    cohere_api_key: str | None = None
    wtw_rerank_model: str = "rerank-v4.0-fast"

    # --- Tavily (external/trends.py) ------------------------------------------
    tavily_api_key: str | None = None

    # --- LangSmith tracing — mandatory on every LLM/retrieval call -----------
    langsmith_api_key: str | None = None
    langsmith_tracing: bool = True
    langsmith_project: str = "whattowear-rag"

    # --- Qdrant (vector store) -------------------------------------------------
    wtw_qdrant_url: str | None = "http://localhost:6333"

    # --- Corpus ingestion (constitution X: no absolute path, no `~`) ---------
    corpus_local_dir: str | None = None

    # --- LangGraph checkpointer pool (memory/store.py) ------------------------
    wtw_checkpointer_pool_max: int = 5

    @property
    def judge_model(self) -> str:
        return self.wtw_judge_model or self.wtw_chat_model

    @property
    def vision_model(self) -> str:
        return self.wtw_vision_model or self.wtw_chat_model


@lru_cache
def get_settings() -> Settings:
    """Reads and validates the environment on first call, then caches the
    result. Raises `pydantic.ValidationError` if `DATABASE_URL` is missing —
    but only when this function is actually called, never on import."""
    return Settings()  # type: ignore[call-arg]
