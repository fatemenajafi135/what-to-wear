"""Unit tests for `SupabaseSessionRepository` against a mocked session (no
database). Real-database RLS+GRANT isolation is covered by
`tests/integration/test_sessions_rls.py`.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

import pytest

from whattowear.repositories import supabase_sessions
from whattowear.repositories.supabase_sessions import SupabaseSessionRepository


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

        monkeypatch.setattr(supabase_sessions, "_session_scope", _scope)

    return _patch


class TestUpsertSession:
    def test_inserts_and_commits(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        upsert_result = MagicMock()
        session = _fake_session([set_config_result, upsert_result])
        patch_session_scope(session)

        repo = SupabaseSessionRepository()
        repo.upsert_session(user_id="user-a", thread_id="thread-1")

        assert session.commit.called
        upsert_call = session.execute.call_args_list[1]
        assert "ON CONFLICT" in upsert_call.args[0].text
        assert upsert_call.args[1] == {"thread_id": "thread-1", "user_id": "user-a"}


class TestInsertMessage:
    def test_returns_new_id_and_commits(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        insert_result = MagicMock()
        insert_result.fetchone.return_value = _FakeRow({"id": "11111111-1111-1111-1111-111111111111"})
        session = _fake_session([set_config_result, insert_result])
        patch_session_scope(session)

        repo = SupabaseSessionRepository()
        message_id = repo.insert_message(
            user_id="user-a",
            session_id="thread-1",
            kind="user_message",
            text_="Something for a rainy commute",
        )

        assert message_id == "11111111-1111-1111-1111-111111111111"
        assert session.commit.called
        insert_call = session.execute.call_args_list[1]
        params = insert_call.args[1]
        assert params["session_id"] == "thread-1"
        assert params["kind"] == "user_message"
        assert params["text"] == "Something for a rainy commute"
        assert params["outfit_ids"] == []

    def test_defaults_text_and_outfit_ids(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        insert_result = MagicMock()
        insert_result.fetchone.return_value = _FakeRow({"id": "message-1"})
        session = _fake_session([set_config_result, insert_result])
        patch_session_scope(session)

        repo = SupabaseSessionRepository()
        repo.insert_message(user_id="user-a", session_id="thread-1", kind="styling_reply")

        params = session.execute.call_args_list[1].args[1]
        assert params["text"] == ""
        assert params["outfit_ids"] == []

    def test_round_trips_outfit_ids(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        insert_result = MagicMock()
        insert_result.fetchone.return_value = _FakeRow({"id": "message-1"})
        session = _fake_session([set_config_result, insert_result])
        patch_session_scope(session)

        repo = SupabaseSessionRepository()
        repo.insert_message(
            user_id="user-a",
            session_id="thread-1",
            kind="styling_reply",
            outfit_ids=["outfit-1", "outfit-2"],
        )

        params = session.execute.call_args_list[1].args[1]
        assert params["outfit_ids"] == ["outfit-1", "outfit-2"]


class TestListSessions:
    def test_returns_rows_most_recent_first(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        select_result = MagicMock()
        select_result.fetchall.return_value = [_FakeRow({"id": "thread-1"})]
        session = _fake_session([set_config_result, select_result])
        patch_session_scope(session)

        repo = SupabaseSessionRepository()
        rows = repo.list_sessions("user-a")

        assert len(rows) == 1
        select_call = session.execute.call_args_list[1]
        assert "ORDER BY s.updated_at DESC" in select_call.args[0].text
        assert select_call.args[1]["user_id"] == "user-a"

    def test_empty_for_no_sessions(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        select_result = MagicMock()
        select_result.fetchall.return_value = []
        session = _fake_session([set_config_result, select_result])
        patch_session_scope(session)

        repo = SupabaseSessionRepository()
        assert repo.list_sessions("user-a") == []


class TestGetSession:
    def test_returns_row_when_owned(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        select_result = MagicMock()
        row = _FakeRow({"id": "thread-1", "outfit_count": 2})
        select_result.fetchone.return_value = row
        session = _fake_session([set_config_result, select_result])
        patch_session_scope(session)

        repo = SupabaseSessionRepository()
        assert repo.get_session("user-a", "thread-1") is row

    def test_returns_none_for_foreign_or_missing_session(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        select_result = MagicMock()
        select_result.fetchone.return_value = None
        session = _fake_session([set_config_result, select_result])
        patch_session_scope(session)

        repo = SupabaseSessionRepository()
        assert repo.get_session("user-a", "someone-elses-thread") is None


class TestListMessages:
    def test_returns_rows_in_order(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        select_result = MagicMock()
        select_result.fetchall.return_value = [
            _FakeRow({"id": "m1", "kind": "user_message"}),
            _FakeRow({"id": "m2", "kind": "styling_reply"}),
        ]
        session = _fake_session([set_config_result, select_result])
        patch_session_scope(session)

        repo = SupabaseSessionRepository()
        rows = repo.list_messages("user-a", "thread-1")

        assert len(rows) == 2
        select_call = session.execute.call_args_list[1]
        assert "ORDER BY created_at ASC" in select_call.args[0].text
        assert select_call.args[1] == {"session_id": "thread-1", "user_id": "user-a"}

    def test_empty_for_no_messages(self, patch_session_scope) -> None:
        set_config_result = MagicMock()
        select_result = MagicMock()
        select_result.fetchall.return_value = []
        session = _fake_session([set_config_result, select_result])
        patch_session_scope(session)

        repo = SupabaseSessionRepository()
        assert repo.list_messages("user-a", "thread-1") == []
