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

# BOTH `localhost` and `127.0.0.1` are listed deliberately. To a browser they
# are different origins even though they resolve to the same machine, and this
# project sends you to both: Supabase's `site_url` is `http://127.0.0.1:3000`
# and `next.config.ts`'s `allowedDevOrigins` allows 127.0.0.1 (feature 003
# needed that for OAuth), while Playwright and most people typing a URL use
# `localhost`. Listing only one produced a 400 on every preflight from the
# other, which surfaced as the closet's generic "Couldn't load your closet."
# error — invisible to the whole test suite, because Playwright runs on the
# host that happened to work. Ports 3000 (`npm run dev`) and 3100 (the e2e
# suite's own dev server) are both real local origins.
DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3100",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3100",
]


def parse_cors_origins(raw: str | None) -> list[str]:
    """Parse a comma-separated origin list, falling back to local defaults.

    Module-level and pure, taking the raw string rather than a `Settings`,
    because `main.py` has to add `CORSMiddleware` at import time and cannot
    call `get_settings()` there: `Settings` requires `DATABASE_URL`, so that
    would break the zero-env-vars import contract `test_import_safety.py`
    exists to enforce (which lists `whattowear.main` explicitly). `main.py`
    reads `os.getenv("WTW_CORS_ORIGINS")` — which never raises — and hands the
    string here, so the parsing rules live in exactly one place and the
    deployed path and the `Settings` path cannot drift apart.

    Each entry is stripped: `"a.com, b.com"` after a comma-space would
    otherwise yield `" b.com"`, which never matches a browser's `Origin`
    header and fails silently — no error anywhere, just rejected requests.
    An empty or whitespace-only value falls back to the defaults rather than
    producing an empty allow-list, which would reject everything including
    local development.
    """
    if not raw:
        return list(DEFAULT_CORS_ORIGINS)
    origins = [origin.strip() for origin in raw.split(",")]
    return [origin for origin in origins if origin] or list(DEFAULT_CORS_ORIGINS)


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
    # How `kb.get_kb()` obtains the knowledge base (feature 017 — deployment).
    #   "corpus"    — read CORPUS_LOCAL_DIR from disk, then build or reconnect
    #                 against Qdrant. The original, evaluated behaviour.
    #   "reconnect" — attach to an already-populated Qdrant collection and
    #                 rebuild the chunk list from stored payloads. Never reads
    #                 the corpus, so a deployed instance does not need it.
    #   "auto"      — same as "corpus". It does NOT fall back to "reconnect"
    #                 when CORPUS_LOCAL_DIR is unset: attaching to a collection
    #                 this process did not build is an operational choice, not
    #                 something to infer from a missing variable.
    # Explicit modes rather than a silent fallback, for the same reason
    # `wtw_checkpointer_mode` has them (docs/design-decisions.md §55).
    wtw_kb_mode: str = "auto"
    wtw_chunk_size: int = 900
    wtw_chunk_overlap: int = 120
    wtw_qdrant_timeout: int = 120
    wtw_qdrant_batch_size: int = 32

    # --- LangGraph checkpointer pool (memory/store.py) ------------------------
    wtw_checkpointer_pool_max: int = 5
    # Mode for checkpointer initialization. Prevents silent fallback to RAM on
    # misconfiguration (e.g., forgetting DATABASE_URL on a cloud service).
    # Options:
    #   "auto" (default): use Postgres if DATABASE_URL is set and reachable;
    #     otherwise use InMemorySaver (for local dev).
    #   "memory": explicitly use InMemorySaver (no Postgres).
    #   "postgres": require DATABASE_URL to be set and reachable; fail if missing.
    wtw_checkpointer_mode: str = "auto"

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

    # --- Photo to items (feature 018) --------------------------------------------
    # Maximum garments accepted from one photo (spec.md FR-002) — bounds worst-case
    # detection call cost/latency and how many review cards one batch asks a user
    # to page through. Enforced in Python (vision.py), not the JSON schema
    # (research.md §3).
    wtw_max_detections_per_photo: int = 8
    # Which IsolationClient adapter (adapters/isolation.py) the extract route
    # uses. "segmentation" is the working default (fastest/cheapest of the
    # three, research.md §5) — spec.md FR-016 requires this be confirmed
    # against real measured data (eval/vision_harness.py --isolation-report),
    # not assumed; see docs/design-decisions.md §62 (PENDING until that run
    # happens).
    wtw_isolation_strategy: str = "segmentation"
    # Per-detection timeout for one isolate() call (research.md §5) — treated
    # identically to any other isolation failure (FR-013's fallback), not
    # surfaced differently.
    wtw_isolation_timeout_seconds: float = 8.0
    # Hybrid's escalation-to-generative trigger (research.md §6): the
    # segmentation mask's area, as a fraction of the frame, below/above which
    # the result is treated as degenerate ("found nothing" / "found
    # everything"). Both PROVISIONAL — tuned from real eval/vision_harness.py
    # --isolation-report numbers once the fixture corpus exists (§62).
    wtw_isolation_hybrid_min_area: float = 0.03
    wtw_isolation_hybrid_max_area: float = 0.92
    # Hosted background-removal endpoint for the segmentation strategy.
    # Unset until a real provider is chosen and an account provisioned
    # (research.md §5's "open item") — same optional-until-used posture as
    # cohere_api_key/tavily_api_key above; get_settings() must not fail for a
    # caller that never touches isolation.
    wtw_segmentation_api_url: str | None = None
    wtw_segmentation_api_key: str | None = None
    # Image-generation-capable model for the generative strategy, routed
    # through the existing AI Gateway (adapters/llm_gateway.get_image_model)
    # — no second LLM client. Defaults to wtw_chat_model if unset, mirroring
    # wtw_vision_model's existing fallback pattern (vision.py).
    wtw_generative_isolation_model: str | None = None

    # --- CORS (feature 017) — deployment readiness --------------------------------
    # Comma-separated list of allowed origins. Optional; unset means the local
    # development defaults. Parsing lives in the module-level
    # `parse_cors_origins()` below, NOT here — see that function's docstring for
    # why `main.py` cannot reach this field.
    wtw_cors_origins: str | None = None

    @property
    def cors_allowed_origins(self) -> list[str]:
        """The parsed allow-list, for any caller that already holds a `Settings`.

        `main.py` deliberately does NOT use this — it has no `Settings` at
        import time. Both paths share `parse_cors_origins()` so they can never
        disagree."""
        return parse_cors_origins(self.wtw_cors_origins)

    @property
    def judge_model(self) -> str:
        return self.wtw_judge_model or self.wtw_chat_model

    @property
    def vision_model(self) -> str:
        return self.wtw_vision_model or self.wtw_chat_model

    @property
    def generative_isolation_model(self) -> str:
        return self.wtw_generative_isolation_model or self.wtw_chat_model


@lru_cache
def get_settings() -> Settings:
    """Reads and validates the environment on first call, then caches the
    result. Raises `pydantic.ValidationError` if `DATABASE_URL` is missing —
    but only when this function is actually called, never on import."""
    return Settings()  # type: ignore[call-arg]
