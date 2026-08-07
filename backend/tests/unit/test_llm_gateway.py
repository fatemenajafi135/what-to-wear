"""adapters/llm_gateway.py — factories raise clearly on missing config,
never touch the network, never read the environment at import time."""

from __future__ import annotations

import pytest

from whattowear.adapters import llm_gateway
from whattowear.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_get_chat_model_raises_without_langsmith_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # `.setenv(..., "")`, not `.delenv` — pydantic-settings falls back to
    # backend/.env's real value for any var that's merely *unset* in
    # os.environ, so the negative case has to override it explicitly.
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("LANGSMITH_API_KEY", "")
    with pytest.raises(RuntimeError, match="LANGSMITH_API_KEY"):
        llm_gateway.get_chat_model()


def test_get_chat_model_raises_without_gateway_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "")
    monkeypatch.setenv("VERCEL_OIDC_TOKEN", "")
    with pytest.raises(RuntimeError, match="gateway key"):
        llm_gateway.get_chat_model()


def test_get_reranker_raises_without_langsmith_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("LANGSMITH_API_KEY", "")
    with pytest.raises(RuntimeError, match="LANGSMITH_API_KEY"):
        llm_gateway.get_reranker()
