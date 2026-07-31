"""Integration tests for the calendar routes (specs/012-calendar/
contracts/calendar.md). Runs against a real local Postgres — no mocked
database layer, matching test_closet_routes.py's precedent. Requires
`DATABASE_URL` pointed at a running Postgres with migration `0004` applied.

Identity is supplied via a FastAPI dependency override (`get_current_user_id`
is already covered by tests/integration/test_whoami.py). RLS's own
guarantee — which this backend's connection doesn't benefit from directly
(BYPASSRLS) — is proven independently by test_calendar_rls.py.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from whattowear.auth import get_current_user_id
from whattowear.core.config import get_settings
from whattowear.core.db import get_engine
from whattowear.main import app

USER_A = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def _authenticated_as_user_a() -> Iterator[None]:
    app.dependency_overrides[get_current_user_id] = lambda: USER_A
    yield
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture(autouse=True)
def _clean_up_rows() -> Iterator[None]:
    yield
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM calendar_connections WHERE user_id = :u"), {"u": USER_A})
        conn.execute(text("DELETE FROM calendar_oauth_attempts WHERE user_id = :u"), {"u": USER_A})
        conn.execute(text("DELETE FROM picked_events WHERE user_id = :u"), {"u": USER_A})


def test_missing_token_rejected() -> None:
    app.dependency_overrides.pop(get_current_user_id, None)
    with TestClient(app) as client:
        response = client.get("/api/v1/calendar/connection")
    assert response.status_code == 401


def test_fresh_user_is_disconnected() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/calendar/connection")
    assert response.status_code == 200
    assert response.json() == {"connected": False, "connected_at": None}


def test_connected_user_reflects_true(monkeypatch: pytest.MonkeyPatch) -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO calendar_connections"
                " (user_id, access_token_encrypted, refresh_token_encrypted, token_expires_at)"
                " VALUES (:u, 'ciphertext-a', 'ciphertext-r', now() + interval '1 hour')"
            ),
            {"u": USER_A},
        )
    with TestClient(app) as client:
        response = client.get("/api/v1/calendar/connection")
    assert response.status_code == 200
    assert response.json()["connected"] is True
    assert response.json()["connected_at"] is not None


def test_events_returns_409_when_disconnected() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/calendar/events")
    assert response.status_code == 409


def test_disconnect_is_idempotent() -> None:
    with TestClient(app) as client:
        first = client.post("/api/v1/calendar/disconnect")
        second = client.post("/api/v1/calendar/disconnect")
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == {"connected": False, "connected_at": None}


def test_disconnect_clears_picked_event() -> None:
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO picked_events (user_id, google_event_id, title, start_time)"
                " VALUES (:u, 'evt-1', 'Dinner', now())"
            ),
            {"u": USER_A},
        )
    with TestClient(app) as client:
        client.post("/api/v1/calendar/disconnect")
        response = client.get("/api/v1/calendar/picked-event")
    assert response.json() == {"picked": False, "event": None}


def test_connect_start_returns_503_when_google_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post("/api/v1/calendar/connect/start")
    get_settings.cache_clear()
    assert response.status_code == 503
    assert "credential" not in response.json()["detail"].lower()


def test_connect_finish_returns_400_for_unknown_state() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/calendar/connect/finish", json={"code": "abc", "state": str(uuid.uuid4())})
    assert response.status_code == 400
    assert response.json() == {"detail": "Could not complete calendar connection"}


def test_picked_event_round_trip() -> None:
    with TestClient(app) as client:
        empty = client.get("/api/v1/calendar/picked-event")
        assert empty.json() == {"picked": False, "event": None}

        put_response = client.put(
            "/api/v1/calendar/picked-event",
            json={
                "google_event_id": "evt-1",
                "title": "Dinner with Sam",
                "start": "2026-08-01T19:30:00Z",
                "location": "Tanto",
            },
        )
        assert put_response.status_code == 200
        assert put_response.json()["picked"] is True
        assert put_response.json()["event"]["title"] == "Dinner with Sam"

        get_response = client.get("/api/v1/calendar/picked-event")
        assert get_response.json()["event"]["google_event_id"] == "evt-1"


def test_picked_event_with_no_location_omits_it_cleanly() -> None:
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/calendar/picked-event",
            json={
                "google_event_id": "evt-2",
                "title": "Focus block",
                "start": "2026-08-02T09:00:00Z",
                "location": None,
            },
        )
    assert response.status_code == 200
    assert response.json()["event"]["location"] is None
