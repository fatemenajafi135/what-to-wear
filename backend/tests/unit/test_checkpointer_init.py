"""Tests for checkpointer initialization modes, especially dev vs misconfiguration."""

from __future__ import annotations

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from whattowear.core.config import Settings
from whattowear.memory.store import get_checkpointer


def test_checkpointer_memory_mode_uses_in_memory_saver() -> None:
    """Explicit wtw_checkpointer_mode='memory' always uses InMemorySaver."""
    # Mock settings with memory mode
    from unittest.mock import patch

    from whattowear.memory import store

    # Clear the singleton
    store._checkpointer = None

    settings = Settings(
        database_url="postgresql://dummy:dummy@localhost/dummy",
        supabase_url="http://localhost:54321",
        wtw_checkpointer_mode="memory",
    )

    with patch("whattowear.memory.store.get_settings", return_value=settings):
        checkpointer = get_checkpointer()
        assert isinstance(checkpointer, InMemorySaver)


def test_checkpointer_auto_mode_no_db_uses_in_memory() -> None:
    """In 'auto' mode, missing DATABASE_URL falls back to InMemorySaver."""
    from unittest.mock import patch

    from whattowear.memory import store

    # Clear the singleton
    store._checkpointer = None

    settings = Settings(
        database_url="",  # No database URL
        supabase_url="http://localhost:54321",
        wtw_checkpointer_mode="auto",
    )

    with patch("whattowear.memory.store.get_settings", return_value=settings):
        checkpointer = get_checkpointer()
        assert isinstance(checkpointer, InMemorySaver)


def test_checkpointer_postgres_mode_no_db_raises_error() -> None:
    """In 'postgres' mode, missing DATABASE_URL raises RuntimeError."""
    from unittest.mock import patch

    from whattowear.memory import store

    # Clear the singleton
    store._checkpointer = None

    settings = Settings(
        database_url="",  # No database URL
        supabase_url="http://localhost:54321",
        wtw_checkpointer_mode="postgres",
    )

    with patch("whattowear.memory.store.get_settings", return_value=settings):
        with pytest.raises(RuntimeError, match="wtw_checkpointer_mode is 'postgres' but no DATABASE_URL"):
            get_checkpointer()


def test_checkpointer_invalid_mode_raises_error() -> None:
    """Unknown wtw_checkpointer_mode raises ValueError."""
    from unittest.mock import patch

    from whattowear.memory import store

    # Clear the singleton
    store._checkpointer = None

    settings = Settings(
        database_url="postgresql://dummy:dummy@localhost/dummy",
        supabase_url="http://localhost:54321",
        wtw_checkpointer_mode="invalid_mode",
    )

    with patch("whattowear.memory.store.get_settings", return_value=settings):
        with pytest.raises(ValueError, match="Invalid wtw_checkpointer_mode"):
            get_checkpointer()


def test_checkpointer_is_singleton() -> None:
    """get_checkpointer() returns the same instance on repeated calls."""
    from unittest.mock import patch

    from whattowear.memory import store

    # Clear the singleton
    store._checkpointer = None

    settings = Settings(
        database_url="",
        supabase_url="http://localhost:54321",
        wtw_checkpointer_mode="memory",
    )

    with patch("whattowear.memory.store.get_settings", return_value=settings):
        cp1 = get_checkpointer()
        cp2 = get_checkpointer()
        assert cp1 is cp2
