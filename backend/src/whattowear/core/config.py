"""Application settings, loaded from the environment on first use.

`get_settings()` is the only way to read configuration. There is no
module-level `Settings()` instance: constructing one eagerly would make
`import whattowear` require `DATABASE_URL` to be set, reproducing the legacy
`db.py` defect this package exists to avoid (see
specs/002-backend-foundation/research.md §1). `lru_cache` gives the
"construct once, reuse" behaviour a module-level singleton would have,
without paying for it at import time.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    log_level: str = "INFO"
    environment: str = "development"
    supabase_url: str
    supabase_jwt_aud: str = "authenticated"


@lru_cache
def get_settings() -> Settings:
    """Reads and validates the environment on first call, then caches the
    result. Raises `pydantic.ValidationError` if `DATABASE_URL` is missing —
    but only when this function is actually called, never on import."""
    return Settings()  # type: ignore[call-arg]
