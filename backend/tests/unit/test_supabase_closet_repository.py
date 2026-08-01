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
from whattowear.schema import CreateWardrobeItemFromUploadRequest, WardrobeItemPatch


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
    "favorite": False,
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


class TestUpdateWardrobeItem:
    def test_partial_patch_issues_update_then_refetches(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        update_result = MagicMock()
        select_result = MagicMock()
        select_result.fetchone.return_value = _FakeRow(_ROW)
        session = _fake_session([set_config_result, update_result, select_result])
        patch_session_scope(session)

        repo = SupabaseClosetRepository()
        item = repo.update_wardrobe_item("user-a", _ROW["id"], WardrobeItemPatch(name="New name"))

        assert item is not None
        assert session.commit.called
        # Second execute call is the UPDATE — assert only the changed field
        # reached the SQL params, not every WardrobeItemPatch field.
        update_call = session.execute.call_args_list[1]
        assert update_call.args[1] == {"name": "New name", "user_id": "user-a", "item_id": _ROW["id"]}

    def test_empty_patch_skips_update_and_still_refetches(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        select_result = MagicMock()
        select_result.fetchone.return_value = _FakeRow(_ROW)
        session = _fake_session([set_config_result, select_result])
        patch_session_scope(session)

        repo = SupabaseClosetRepository()
        item = repo.update_wardrobe_item("user-a", _ROW["id"], WardrobeItemPatch())

        assert item is not None
        assert session.execute.call_count == 2  # set_config + SELECT only, no UPDATE
        assert not session.commit.called

    def test_returns_none_for_foreign_or_missing_item(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        update_result = MagicMock()
        select_result = MagicMock()
        select_result.fetchone.return_value = None
        session = _fake_session([set_config_result, update_result, select_result])
        patch_session_scope(session)

        repo = SupabaseClosetRepository()
        item = repo.update_wardrobe_item("user-a", "someone-elses-id", WardrobeItemPatch(name="x"))
        assert item is None


class TestToggleFavorite:
    def test_flips_and_returns_new_value(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        update_result = MagicMock()
        update_result.fetchone.return_value = _FakeRow({"favorite": True})
        session = _fake_session([set_config_result, update_result])
        patch_session_scope(session)

        repo = SupabaseClosetRepository()
        favorite = repo.toggle_favorite("user-a", _ROW["id"])
        assert favorite is True
        assert session.commit.called

    def test_returns_none_for_foreign_or_missing_item(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        update_result = MagicMock()
        update_result.fetchone.return_value = None
        session = _fake_session([set_config_result, update_result])
        patch_session_scope(session)

        repo = SupabaseClosetRepository()
        assert repo.toggle_favorite("user-a", "someone-elses-id") is None


class TestRecordWear:
    def test_inserts_upsert_when_owned(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        ownership_result = MagicMock()
        ownership_result.fetchone.return_value = (1,)
        insert_result = MagicMock()
        session = _fake_session([set_config_result, ownership_result, insert_result])
        patch_session_scope(session)

        repo = SupabaseClosetRepository()
        assert repo.record_wear("user-a", _ROW["id"]) is True
        assert session.commit.called
        insert_call = session.execute.call_args_list[2]
        assert "ON CONFLICT (item_id, worn_date) DO NOTHING" in insert_call.args[0].text

    def test_returns_false_for_foreign_or_missing_item_without_inserting(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        ownership_result = MagicMock()
        ownership_result.fetchone.return_value = None
        session = _fake_session([set_config_result, ownership_result])
        patch_session_scope(session)

        repo = SupabaseClosetRepository()
        assert repo.record_wear("user-a", "someone-elses-id") is False
        assert session.execute.call_count == 2  # no INSERT attempted
        assert not session.commit.called


class TestDeleteWardrobeItem:
    def test_returns_true_when_a_row_was_deleted(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        delete_result = MagicMock(rowcount=1)
        session = _fake_session([set_config_result, delete_result])
        patch_session_scope(session)

        repo = SupabaseClosetRepository()
        assert repo.delete_wardrobe_item("user-a", _ROW["id"]) is True
        assert session.commit.called

    def test_returns_false_when_no_row_matched(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        delete_result = MagicMock(rowcount=0)
        session = _fake_session([set_config_result, delete_result])
        patch_session_scope(session)

        repo = SupabaseClosetRepository()
        assert repo.delete_wardrobe_item("user-a", "someone-elses-id") is False


class TestCreateWardrobeItemFromUpload:
    def test_detected_attributes_are_never_replaced_by_defaults(self, patch_session_scope) -> None:
        """This method used to substitute casual/3/all-four-seasons whenever
        the request omitted them, and the frontend was omitting them — so
        every photo-added item stored the same three fabricated values
        regardless of what the VLM detected (design-decisions.md §30). The
        request model now requires them; nothing here may rewrite them."""
        set_config_result = MagicMock()
        insert_result = MagicMock()
        insert_result.fetchone.return_value = _FakeRow(
            {**_ROW, "formality": "black_tie", "warmth": 0, "season": ["summer"]}
        )
        session = _fake_session([set_config_result, insert_result])
        patch_session_scope(session)

        request = CreateWardrobeItemFromUploadRequest(
            photo_path="user-a/abc-shirt.jpg",
            category="top",
            colors=["#1b2a4a"],
            formality="black_tie",
            warmth=0,
            season=["summer"],
        )
        repo = SupabaseClosetRepository()
        repo.create_wardrobe_item_from_upload("user-a", request)

        params = session.execute.call_args_list[1].args[1]
        assert params["formality"] == "black_tie"
        assert params["warmth"] == 0
        assert params["season"] == ["summer"]

    def test_supplied_attributes_pass_through_unchanged(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        insert_result = MagicMock()
        insert_result.fetchone.return_value = _FakeRow(_ROW)
        session = _fake_session([set_config_result, insert_result])
        patch_session_scope(session)

        request = CreateWardrobeItemFromUploadRequest(
            photo_path="user-a/abc-shirt.jpg",
            category="top",
            colors=["#1b2a4a"],
            formality="formal",
            warmth=5,
            season=["winter"],
            fabric="wool",
            pattern="solid",
            fit="slim",
            name="My blazer",
            notes="Dry clean only",
        )
        repo = SupabaseClosetRepository()
        repo.create_wardrobe_item_from_upload("user-a", request)

        insert_call = session.execute.call_args_list[1]
        params = insert_call.args[1]
        assert params["formality"] == "formal"
        assert params["warmth"] == 5
        assert params["season"] == ["winter"]
        assert params["fabric"] == "wool"
        assert params["name"] == "My blazer"
        assert params["notes"] == "Dry clean only"
