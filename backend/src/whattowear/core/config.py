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

    # --- Calendar (feature 012) — token encryption + app-orchestrated Google OAuth --------
    # Optional: each adapter/repository call site raises its own clear error when actually
    # needed and unset, mirroring the AI-layer key pattern above — get_settings() itself must
    # never fail for a caller that doesn't touch calendar code.
    wtw_token_encryption_key: str | None = None
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str | None = None

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
    # Unset locally (infra/docker-compose.yml's container needs no auth); a
    # production cloud instance would set this.
    wtw_qdrant_api_key: str | None = None

    # --- Corpus ingestion (constitution X: no absolute path, no `~`) ---------
    corpus_local_dir: str | None = None
    wtw_chunk_size: int = 900
    wtw_chunk_overlap: int = 120
    wtw_qdrant_timeout: int = 120
    wtw_qdrant_batch_size: int = 32

    # --- LangGraph checkpointer pool (memory/store.py) ------------------------
    wtw_checkpointer_pool_max: int = 5

    # --- Closet (feature 004) --------------------------------------------------
    wtw_closet_page_size: int = 20

    # --- Photo upload + vision (feature 006) ------------------------------------
    # Enforced in the extract route before a file is read or forwarded to
    # Storage/the VLM (specs/006-photo-upload-vision/research.md §3). The
    # wardrobe-photos bucket's own file_size_limit in config.toml is a second,
    # independent backstop at the Storage layer.
    wtw_max_upload_bytes: int = 10_485_760
    # TTL for signed URLs minted at closet-read time (research.md §2) — never
    # stored, just how long a photo_url stays valid before the next fetch
    # (e.g. re-navigating to /closet) mints a fresh one.
    wtw_photo_signed_url_ttl_seconds: int = 3600

    # --- Styling chat (feature 008) ---------------------------------------------
    # design-decisions.md §11's three-band gate: below the floor, blocked; below
    # the sparse threshold, allowed with a dismissible expectation-setting banner.
    wtw_wardrobe_min_items: int = 5
    wtw_wardrobe_sparse_threshold: int = 15
    # Backstop only, not a UX-driven cap (spec.md Clarifications, research.md §3)
    # — bounds a genuinely stuck request, not ordinary multi-second latency.
    wtw_styling_request_timeout_seconds: int = 120

    # --- Conversational turns (feature 016) --------------------------------------
    # Lifetime per thread, not reset by a "Start styling" tap (design-decisions.md
    # §48) — counted from existing `messages` rows, not a separate counter.
    wtw_conversation_turn_cap: int = 6

    # --- CORS (feature 017) — deployment readiness --------------------------------
    # Comma-separated list of allowed origins for CORS. Optional; if unset, defaults
    # to localhost origins for local development. Each origin is stripped of whitespace
    # and empty entries are filtered. Read via .cors_allowed_origins property.
    wtw_cors_origins: str | None = None

    @property
    def cors_allowed_origins(self) -> list[str]:
        """Parsed and validated CORS allowed origins.

        Defaults to localhost origins for development. In production,
        set wtw_cors_origins to a comma-separated list of allowed origins.
        Each origin is stripped of leading/trailing whitespace; empty entries
        are filtered out."""
        if not self.wtw_cors_origins:
            return self._default_cors_origins()
        origins = [o.strip() for o in self.wtw_cors_origins.split(",")]
        filtered = [o for o in origins if o]
        return filtered if filtered else self._default_cors_origins()

    @staticmethod
    def _default_cors_origins() -> list[str]:
        """Default CORS origins for development."""
        return [
            "http://localhost:3000",
            "http://localhost:3100",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3100",
        ]

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
