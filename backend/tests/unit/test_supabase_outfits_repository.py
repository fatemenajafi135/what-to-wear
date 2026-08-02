"""Unit tests for `SupabaseOutfitRepository` against a mocked session (no
database). Real-database RLS+GRANT isolation is covered by
`tests/integration/test_outfits_rls.py` and `test_outfit_wears_rls.py`.
"""

from __future__ import annotations

import json
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
            title="Rainy day commute",
        )

        assert outfit_id == "11111111-1111-1111-1111-111111111111"
        assert session.commit.called
        insert_call = session.execute.call_args_list[1]
        params = insert_call.args[1]
        assert params["user_id"] == "user-a"
        assert params["item_ids"] == ["item-1", "item-2"]
        assert params["match_label"] == "great"
        assert params["title"] == "Rainy day commute"
        assert params["rationale_with_citations"] == ""
        assert json.loads(params["citations"]) == []
        assert json.loads(params["dimension_scores"]) == []

    def test_round_trips_citations_and_dimension_scores(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        insert_result = MagicMock()
        insert_result.fetchone.return_value = _FakeRow({"id": "outfit-1"})
        session = _fake_session([set_config_result, insert_result])
        patch_session_scope(session)

        citations = [{"number": 1, "text": "The Style Bible"}]
        dimension_scores = [{"dimension": "color_harmony", "value": 0.82}]

        repo = SupabaseOutfitRepository()
        repo.create(
            user_id="user-a",
            occasion="Dinner",
            meta_line="Dinner · Business casual",
            rationale_text="A cohesive look.",
            match_label="good",
            item_ids=["item-1"],
            title="Dinner",
            rationale_with_citations="A cohesive look. [1]",
            citations=citations,
            dimension_scores=dimension_scores,
        )

        params = session.execute.call_args_list[1].args[1]
        assert params["rationale_with_citations"] == "A cohesive look. [1]"
        assert json.loads(params["citations"]) == citations
        assert json.loads(params["dimension_scores"]) == dimension_scores


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


class TestList:
    def test_returns_rows_for_each_sort(self, patch_session_scope) -> None:
        for sort in ("date", "favorite", "most_worn"):
            set_config_result = MagicMock()
            select_result = MagicMock()
            select_result.fetchall.return_value = [_FakeRow({"id": "outfit-1"})]
            session = _fake_session([set_config_result, select_result])
            patch_session_scope(session)

            repo = SupabaseOutfitRepository()
            rows = repo.list_outfits("user-a", sort=sort)  # type: ignore[arg-type]
            assert len(rows) == 1
            select_call = session.execute.call_args_list[1]
            assert "ORDER BY" in select_call.args[0].text
            assert select_call.args[1]["user_id"] == "user-a"

    def test_empty_for_no_outfits(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        select_result = MagicMock()
        select_result.fetchall.return_value = []
        session = _fake_session([set_config_result, select_result])
        patch_session_scope(session)

        repo = SupabaseOutfitRepository()
        assert repo.list_outfits("user-a") == []


class TestGet:
    def test_returns_row_when_owned(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        select_result = MagicMock()
        row = _FakeRow({"id": "outfit-1", "title": "Dinner"})
        select_result.fetchone.return_value = row
        session = _fake_session([set_config_result, select_result])
        patch_session_scope(session)

        repo = SupabaseOutfitRepository()
        assert repo.get("user-a", "outfit-1") is row

    def test_returns_none_for_foreign_or_missing_outfit(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        select_result = MagicMock()
        select_result.fetchone.return_value = None
        session = _fake_session([set_config_result, select_result])
        patch_session_scope(session)

        repo = SupabaseOutfitRepository()
        assert repo.get("user-a", "someone-elses-outfit") is None


class TestDelete:
    def test_returns_true_when_row_deleted(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        delete_result = MagicMock()
        delete_result.rowcount = 1
        session = _fake_session([set_config_result, delete_result])
        patch_session_scope(session)

        repo = SupabaseOutfitRepository()
        assert repo.delete("user-a", "outfit-1") is True
        assert session.commit.called

    def test_returns_false_for_foreign_or_missing_outfit(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        delete_result = MagicMock()
        delete_result.rowcount = 0
        session = _fake_session([set_config_result, delete_result])
        patch_session_scope(session)

        repo = SupabaseOutfitRepository()
        assert repo.delete("user-a", "someone-elses-outfit") is False


class TestRename:
    def test_returns_new_title(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        update_result = MagicMock()
        update_result.fetchone.return_value = _FakeRow({"title": "Friday client dinner"})
        session = _fake_session([set_config_result, update_result])
        patch_session_scope(session)

        repo = SupabaseOutfitRepository()
        assert repo.rename("user-a", "outfit-1", "Friday client dinner") == "Friday client dinner"
        assert session.commit.called

    def test_returns_none_for_foreign_or_missing_outfit(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        update_result = MagicMock()
        update_result.fetchone.return_value = None
        session = _fake_session([set_config_result, update_result])
        patch_session_scope(session)

        repo = SupabaseOutfitRepository()
        assert repo.rename("user-a", "someone-elses-outfit", "New title") is None


class TestLogWorn:
    def test_writes_outfit_and_item_wears(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        ownership_result = MagicMock()
        ownership_result.fetchone.return_value = (1,)
        outfit_wear_insert = MagicMock()
        item_wear_insert_1 = MagicMock()
        item_wear_insert_2 = MagicMock()
        session = _fake_session(
            [set_config_result, ownership_result, outfit_wear_insert, item_wear_insert_1, item_wear_insert_2]
        )
        patch_session_scope(session)

        repo = SupabaseOutfitRepository()
        assert repo.log_worn("user-a", "outfit-1", ["item-1", "item-2"]) is True
        assert session.commit.called

        outfit_wear_call = session.execute.call_args_list[2]
        assert "outfit_wears" in outfit_wear_call.args[0].text
        item_wear_calls = session.execute.call_args_list[3:5]
        assert all("item_wears" in call.args[0].text for call in item_wear_calls)
        assert {call.args[1]["item_id"] for call in item_wear_calls} == {"item-1", "item-2"}

    def test_skips_writes_for_foreign_or_missing_outfit(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        ownership_result = MagicMock()
        ownership_result.fetchone.return_value = None
        session = _fake_session([set_config_result, ownership_result])
        patch_session_scope(session)

        repo = SupabaseOutfitRepository()
        assert repo.log_worn("user-a", "someone-elses-outfit", ["item-1"]) is False
        assert not session.commit.called

    def test_no_item_writes_when_no_owned_items(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        ownership_result = MagicMock()
        ownership_result.fetchone.return_value = (1,)
        outfit_wear_insert = MagicMock()
        session = _fake_session([set_config_result, ownership_result, outfit_wear_insert])
        patch_session_scope(session)

        repo = SupabaseOutfitRepository()
        assert repo.log_worn("user-a", "outfit-1", []) is True
        assert session.execute.call_count == 3
