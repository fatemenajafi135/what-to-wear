"""Unit tests for `SupabaseCalendarRepository` against a mocked session (no
database) and a mocked `google_calendar` adapter (no network). Real-database
behavior (RLS isolation) is covered by
`tests/integration/test_calendar_rls.py`."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from whattowear.adapters import google_calendar
from whattowear.repositories import supabase_calendar
from whattowear.repositories.supabase_calendar import PickedEventSnapshot, SupabaseCalendarRepository


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

        monkeypatch.setattr(supabase_calendar, "_session_scope", _scope)

    return _patch


@pytest.fixture(autouse=True)
def _fixed_encryption_key(monkeypatch: pytest.MonkeyPatch):
    from cryptography.fernet import Fernet

    from whattowear.adapters import token_encryption
    from whattowear.core.config import get_settings

    get_settings.cache_clear()
    token_encryption._fernet.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")
    monkeypatch.setenv("WTW_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    yield
    get_settings.cache_clear()
    token_encryption._fernet.cache_clear()


class TestGetConnection:
    def test_disconnected_when_no_row(self, patch_session_scope) -> None:
        session = _fake_session([MagicMock(), MagicMock(fetchone=MagicMock(return_value=None))])
        patch_session_scope(session)
        status = SupabaseCalendarRepository().get_connection("user-a")
        assert status.connected is False
        assert status.connected_at is None

    def test_connected_when_row_present(self, patch_session_scope) -> None:
        now = datetime.now(UTC)
        row = _FakeRow({"connected_at": now})
        session = _fake_session([MagicMock(), MagicMock(fetchone=MagicMock(return_value=row))])
        patch_session_scope(session)
        status = SupabaseCalendarRepository().get_connection("user-a")
        assert status.connected is True
        assert status.connected_at == now


class TestStartOauthAttempt:
    def test_inserts_attempt_and_returns_authorize_url(self, patch_session_scope, monkeypatch) -> None:
        session = _fake_session([MagicMock(), MagicMock()])
        patch_session_scope(session)
        monkeypatch.setattr(
            google_calendar,
            "generate_pkce_pair",
            lambda: google_calendar.PkcePair(verifier="v", challenge="c"),
        )
        monkeypatch.setattr(
            google_calendar, "build_authorize_url", lambda state, challenge: f"https://google/{state}/{challenge}"
        )

        state, url = SupabaseCalendarRepository().start_oauth_attempt("user-a")

        assert url == f"https://google/{state}/c"
        insert_call = session.execute.call_args_list[1]
        assert insert_call.args[1]["user_id"] == "user-a"
        assert insert_call.args[1]["code_verifier"] == "v"


class TestFinishOauthAttempt:
    def test_returns_false_when_attempt_not_found(self, patch_session_scope) -> None:
        session = _fake_session([MagicMock(), MagicMock(fetchone=MagicMock(return_value=None))])
        patch_session_scope(session)
        ok = SupabaseCalendarRepository().finish_oauth_attempt("user-a", "state-x", "code-1")
        assert ok is False

    def test_returns_false_when_attempt_belongs_to_another_user(self, patch_session_scope) -> None:
        row = _FakeRow({"user_id": "user-b", "code_verifier": "v"})
        session = _fake_session([MagicMock(), MagicMock(fetchone=MagicMock(return_value=row))])
        patch_session_scope(session)
        ok = SupabaseCalendarRepository().finish_oauth_attempt("user-a", "state-x", "code-1")
        assert ok is False

    def test_returns_false_when_exchange_fails(self, patch_session_scope, monkeypatch) -> None:
        row = _FakeRow({"user_id": "user-a", "code_verifier": "v"})
        session = _fake_session([MagicMock(), MagicMock(fetchone=MagicMock(return_value=row)), MagicMock()])
        patch_session_scope(session)

        def _raise(*_a, **_k):
            raise google_calendar.GoogleCalendarRequestFailed("boom")

        monkeypatch.setattr(google_calendar, "exchange_code_for_tokens", _raise)
        ok = SupabaseCalendarRepository().finish_oauth_attempt("user-a", "state-x", "code-1")
        assert ok is False

    def test_returns_false_when_no_refresh_token_granted(self, patch_session_scope, monkeypatch) -> None:
        row = _FakeRow({"user_id": "user-a", "code_verifier": "v"})
        session = _fake_session([MagicMock(), MagicMock(fetchone=MagicMock(return_value=row)), MagicMock()])
        patch_session_scope(session)
        monkeypatch.setattr(
            google_calendar,
            "exchange_code_for_tokens",
            lambda code, verifier: google_calendar.TokenGrant(
                access_token="at", refresh_token=None, expires_at=datetime.now(UTC)
            ),
        )
        ok = SupabaseCalendarRepository().finish_oauth_attempt("user-a", "state-x", "code-1")
        assert ok is False

    def test_saves_connection_on_success(self, patch_session_scope, monkeypatch) -> None:
        row = _FakeRow({"user_id": "user-a", "code_verifier": "v"})
        lookup_session = _fake_session([MagicMock(), MagicMock(fetchone=MagicMock(return_value=row)), MagicMock()])
        save_session = _fake_session([MagicMock(), MagicMock()])
        sessions = iter([lookup_session, save_session])

        @contextmanager
        def _scope():
            yield next(sessions)

        monkeypatch.setattr(supabase_calendar, "_session_scope", _scope)
        monkeypatch.setattr(
            google_calendar,
            "exchange_code_for_tokens",
            lambda code, verifier: google_calendar.TokenGrant(
                access_token="at", refresh_token="rt", expires_at=datetime.now(UTC) + timedelta(hours=1)
            ),
        )
        ok = SupabaseCalendarRepository().finish_oauth_attempt("user-a", "state-x", "code-1")
        assert ok is True
        insert_call = save_session.execute.call_args_list[1]
        # Stored ciphertext, never the plaintext token.
        assert insert_call.args[1]["access_token"] != "at"


class TestDisconnect:
    def test_deletes_both_connection_and_picked_event(self, patch_session_scope) -> None:
        session = _fake_session([MagicMock(), MagicMock(), MagicMock()])
        patch_session_scope(session)
        SupabaseCalendarRepository().disconnect("user-a")
        queries = [call.args[0].text for call in session.execute.call_args_list]
        assert any("DELETE FROM calendar_connections" in q for q in queries)
        assert any("DELETE FROM picked_events" in q for q in queries)


class TestGetValidAccessToken:
    def test_returns_none_when_not_connected(self, patch_session_scope) -> None:
        session = _fake_session([MagicMock(), MagicMock(fetchone=MagicMock(return_value=None))])
        patch_session_scope(session)
        assert SupabaseCalendarRepository().get_valid_access_token("user-a") is None

    def test_returns_decrypted_token_when_not_expired(self, patch_session_scope) -> None:
        from whattowear.adapters import token_encryption

        ciphertext = token_encryption.encrypt("live-access-token")
        row = _FakeRow(
            {
                "access_token_encrypted": ciphertext,
                "refresh_token_encrypted": token_encryption.encrypt("rt"),
                "token_expires_at": datetime.now(UTC) + timedelta(hours=1),
            }
        )
        session = _fake_session([MagicMock(), MagicMock(fetchone=MagicMock(return_value=row))])
        patch_session_scope(session)
        token = SupabaseCalendarRepository().get_valid_access_token("user-a")
        assert token == "live-access-token"

    def test_refreshes_when_expired(self, patch_session_scope, monkeypatch) -> None:
        from whattowear.adapters import token_encryption

        row = _FakeRow(
            {
                "access_token_encrypted": token_encryption.encrypt("stale"),
                "refresh_token_encrypted": token_encryption.encrypt("rt"),
                "token_expires_at": datetime.now(UTC) - timedelta(hours=1),
            }
        )
        read_session = _fake_session([MagicMock(), MagicMock(fetchone=MagicMock(return_value=row))])
        update_session = _fake_session([MagicMock(), MagicMock()])
        sessions = iter([read_session, update_session])

        @contextmanager
        def _scope():
            yield next(sessions)

        monkeypatch.setattr(supabase_calendar, "_session_scope", _scope)
        monkeypatch.setattr(
            google_calendar,
            "refresh_access_token",
            lambda rt: google_calendar.TokenGrant(
                access_token="fresh", refresh_token=None, expires_at=datetime.now(UTC) + timedelta(hours=1)
            ),
        )
        token = SupabaseCalendarRepository().get_valid_access_token("user-a")
        assert token == "fresh"

    def test_clears_connection_when_refresh_fails(self, patch_session_scope, monkeypatch) -> None:
        from whattowear.adapters import token_encryption

        row = _FakeRow(
            {
                "access_token_encrypted": token_encryption.encrypt("stale"),
                "refresh_token_encrypted": token_encryption.encrypt("rt"),
                "token_expires_at": datetime.now(UTC) - timedelta(hours=1),
            }
        )
        read_session = _fake_session([MagicMock(), MagicMock(fetchone=MagicMock(return_value=row))])
        disconnect_session = _fake_session([MagicMock(), MagicMock(), MagicMock()])
        sessions = iter([read_session, disconnect_session])

        @contextmanager
        def _scope():
            yield next(sessions)

        monkeypatch.setattr(supabase_calendar, "_session_scope", _scope)

        def _raise(*_a, **_k):
            raise google_calendar.GoogleCalendarRequestFailed("refresh failed")

        monkeypatch.setattr(google_calendar, "refresh_access_token", _raise)
        token = SupabaseCalendarRepository().get_valid_access_token("user-a")
        assert token is None
        queries = [call.args[0].text for call in disconnect_session.execute.call_args_list]
        assert any("DELETE FROM calendar_connections" in q for q in queries)


class TestPickedEvent:
    def test_get_returns_none_when_no_row(self, patch_session_scope) -> None:
        session = _fake_session([MagicMock(), MagicMock(fetchone=MagicMock(return_value=None))])
        patch_session_scope(session)
        assert SupabaseCalendarRepository().get_picked_event("user-a") is None

    def test_get_maps_row(self, patch_session_scope) -> None:
        start = datetime.now(UTC)
        row = _FakeRow({"google_event_id": "evt-1", "title": "Dinner", "start_time": start, "location": "Tanto"})
        session = _fake_session([MagicMock(), MagicMock(fetchone=MagicMock(return_value=row))])
        patch_session_scope(session)
        event = SupabaseCalendarRepository().get_picked_event("user-a")
        assert event is not None
        assert event.google_event_id == "evt-1"
        assert event.location == "Tanto"

    def test_set_upserts(self, patch_session_scope) -> None:
        session = _fake_session([MagicMock(), MagicMock()])
        patch_session_scope(session)
        event = PickedEventSnapshot(
            google_event_id="evt-1", title="Dinner", start_time=datetime.now(UTC), location=None
        )
        SupabaseCalendarRepository().set_picked_event("user-a", event)
        insert_call = session.execute.call_args_list[1]
        assert insert_call.args[1]["google_event_id"] == "evt-1"
        assert insert_call.args[1]["location"] is None
