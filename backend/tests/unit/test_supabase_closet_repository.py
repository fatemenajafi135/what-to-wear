"""Unit tests for `SupabaseClosetRepository` — row->`WardrobeItem` mapping
and the derivation-inputs empty-return contract, against a mocked session
(no database). Real-database behavior (RLS isolation, actual SQL) is covered
by `tests/integration/test_closet_routes.py` and
`tests/integration/test_wardrobe_rls.py`.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

from whattowear.repositories import supabase_closet
from whattowear.repositories.supabase_closet import SupabaseClosetRepository


class _FakeRow:
    def __init__(self, mapping: dict[str, Any]) -> None:
        self._mapping = mapping


def _fake_session(execute_results: list[Any]) -> MagicMock:
    """A mock Session whose `.execute(...)` returns successive results from
    `execute_results` in call order (first call is always the
    `set_config` claim-setting statement when a user_id is involved)."""
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

        monkeypatch.setattr(supabase_closet, "_session_scope", _scope)

    return _patch


_ROW = {
    "id": "11111111-1111-1111-1111-111111111111",
    "category": "top",
    "colors": ["#1b2a4a"],
    "formality": "casual",
    "warmth": 1,
    "season": ["spring"],
    "fabric": "cotton",
    "pattern": None,
    "fit": None,
    "name": "Navy tee",
    "notes": "A bit worn",
    "source": "upload",
    "photo_path": None,
}


class TestListWardrobeItems:
    def test_maps_row_to_wardrobe_item_including_name_and_notes(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        select_result = MagicMock()
        select_result.fetchall.return_value = [_FakeRow(_ROW)]
        session = _fake_session([set_config_result, select_result])
        patch_session_scope(session)

        repo = SupabaseClosetRepository()
        items = repo.list_wardrobe_items("user-a")

        assert len(items) == 1
        item = items[0]
        assert item.id == _ROW["id"]
        assert item.name == "Navy tee"
        assert item.notes == "A bit worn"
        assert item.colors == ["#1b2a4a"]

    def test_empty_result_returns_empty_list(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        select_result = MagicMock()
        select_result.fetchall.return_value = []
        session = _fake_session([set_config_result, select_result])
        patch_session_scope(session)

        repo = SupabaseClosetRepository()
        assert repo.list_wardrobe_items("user-a") == []


class TestGetWardrobeItem:
    def test_returns_none_when_no_row(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        select_result = MagicMock()
        select_result.fetchone.return_value = None
        session = _fake_session([set_config_result, select_result])
        patch_session_scope(session)

        repo = SupabaseClosetRepository()
        assert repo.get_wardrobe_item("user-a", "missing-id") is None

    def test_returns_item_when_row_present(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        select_result = MagicMock()
        select_result.fetchone.return_value = _FakeRow(_ROW)
        session = _fake_session([set_config_result, select_result])
        patch_session_scope(session)

        repo = SupabaseClosetRepository()
        item = repo.get_wardrobe_item("user-a", _ROW["id"])
        assert item is not None
        assert item.id == _ROW["id"]


class TestListCatalogItems:
    def test_source_is_forced_to_catalog(self, patch_session_scope) -> None:
        row = dict(_ROW)
        row["source"] = "catalog"
        select_result = MagicMock()
        select_result.fetchall.return_value = [_FakeRow(row)]
        session = _fake_session([select_result])
        patch_session_scope(session)

        repo = SupabaseClosetRepository()
        items = repo.list_catalog_items()
        assert len(items) == 1
        assert items[0].source == "catalog"


class TestGetDerivationInputs:
    def test_always_empty(self) -> None:
        repo = SupabaseClosetRepository()
        feedback, dismissals = repo.get_derivation_inputs("any-user-id")
        assert feedback == []
        assert dismissals == {}
