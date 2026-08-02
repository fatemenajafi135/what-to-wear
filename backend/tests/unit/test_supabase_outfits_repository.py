"""Unit tests for `SupabaseOutfitRepository` against a mocked session (no
database). Real-database RLS+GRANT isolation is covered by
`tests/integration/test_outfits_isolation.py`.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

from whattowear.repositories import supabase_outfits
from whattowear.repositories.supabase_outfits import SupabaseOutfitRepository


class _FakeRow:
    def __init__(self, mapping: dict[str, Any]) -> None:
        self._mapping = mapping


def _fake_session(execute_results: list[Any]) -> MagicMock:
    session = MagicMock()
    results = iter(execute_results)

    def _execute(*_args: Any, **_kwargs: Any) -> Any:
        return next(results)

    session.execute.side_effect = _execute
    return session


@pytest.fixture
def patch_session_scope(monkeypatch: pytest.MonkeyPatch):
    def _patch(session: MagicMock) -> None:
        @contextmanager
        def _scope():
            yield session

        monkeypatch.setattr(supabase_outfits, "_session_scope", _scope)

    return _patch


class TestCreate:
    def test_returns_new_id_and_commits(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        insert_result = MagicMock()
        insert_result.fetchone.return_value = _FakeRow({"id": "11111111-1111-1111-1111-111111111111"})
        session = _fake_session([set_config_result, insert_result])
        patch_session_scope(session)

        repo = SupabaseOutfitRepository()
        outfit_id = repo.create(
            user_id="user-a",
            occasion="Rainy day commute",
            meta_line="Rainy day commute · Business casual",
            rationale_text="A cohesive, weather-ready look.",
            match_label="great",
            item_ids=["item-1", "item-2"],
        )

        assert outfit_id == "11111111-1111-1111-1111-111111111111"
        assert session.commit.called
        insert_call = session.execute.call_args_list[1]
        params = insert_call.args[1]
        assert params["user_id"] == "user-a"
        assert params["item_ids"] == ["item-1", "item-2"]
        assert params["match_label"] == "great"


class TestToggleFavorite:
    def test_flips_and_returns_new_value(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        update_result = MagicMock()
        update_result.fetchone.return_value = _FakeRow({"favorite": False})
        session = _fake_session([set_config_result, update_result])
        patch_session_scope(session)

        repo = SupabaseOutfitRepository()
        favorite = repo.toggle_favorite("user-a", "outfit-1")
        assert favorite is False
        assert session.commit.called

    def test_returns_none_for_foreign_or_missing_outfit(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        update_result = MagicMock()
        update_result.fetchone.return_value = None
        session = _fake_session([set_config_result, update_result])
        patch_session_scope(session)

        repo = SupabaseOutfitRepository()
        assert repo.toggle_favorite("user-a", "someone-elses-outfit") is None
