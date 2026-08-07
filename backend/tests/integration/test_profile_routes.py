"""Integration tests for the /api/v1/profile routes (feature 013).

Runs against a real database (see tests/integration/conftest.py) — no mocked repository
layer, matching test_health.py's precedent (research.md §8 in 002-backend-foundation). JWT
verification is mocked exactly as in test_whoami.py, since exercising a real Supabase JWKS
endpoint is out of scope for this test's purpose (route + persistence behavior, not auth
verification itself — that's whoami's job).
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from whattowear import auth
from whattowear.core.db import get_engine
from whattowear.main import app


def _mock_token_as(mocker, user_id: str) -> None:
    fake_signing_key = mocker.Mock(key="fake-public-key")
    mocker.patch.object(
        auth,
        "_get_jwk_client",
        return_value=mocker.Mock(get_signing_key_from_jwt=mocker.Mock(return_value=fake_signing_key)),
    )
    mocker.patch.object(auth, "jwt_decode", return_value={"sub": user_id, "aud": "authenticated"})


@pytest.fixture
def user_a() -> str:
    return _insert_auth_user()


@pytest.fixture
def user_b() -> str:
    return _insert_auth_user()


def _insert_auth_user() -> str:
    user_id = str(uuid.uuid4())
    with get_engine().begin() as conn:
        conn.execute(text("insert into auth.users (id) values (:id)"), {"id": user_id})
    return user_id


def _client() -> TestClient:
    return TestClient(app, headers={"Authorization": "Bearer fake.jwt.token"})


def test_missing_token_rejected() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/profile")

    assert response.status_code == 401


def test_new_user_gets_all_defaults(mocker, user_a: str) -> None:
    _mock_token_as(mocker, user_a)

    with _client() as client:
        response = client.get("/api/v1/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["style_tags"] == []
    assert body["notifications_enabled"] is True
    assert body["body_shape"] is None


def test_style_preferences_persist_across_requests(mocker, user_a: str) -> None:
    _mock_token_as(mocker, user_a)
    payload = {"style_tags": ["Classic", "Minimal"], "colour_tags": ["Pastels"], "brands_to_avoid": ["Brand X"]}

    with _client() as client:
        patch_response = client.patch("/api/v1/profile/style-preferences", json=payload)
        get_response = client.get("/api/v1/profile")

    assert patch_response.status_code == 200
    assert patch_response.json()["style_tags"] == ["Classic", "Minimal"]
    assert get_response.json() == patch_response.json()


def test_out_of_vocabulary_style_tag_rejected(mocker, user_a: str) -> None:
    _mock_token_as(mocker, user_a)
    payload = {"style_tags": ["Not A Tag"], "colour_tags": [], "brands_to_avoid": []}

    with _client() as client:
        response = client.patch("/api/v1/profile/style-preferences", json=payload)

    assert response.status_code == 422


def test_body_size_fields_persist_together(mocker, user_a: str) -> None:
    _mock_token_as(mocker, user_a)
    payload = {
        "body_shape": "hourglass",
        "gender": "woman",
        "birth_date": "1990-05-12",
        "height": "5 ft 6 in",
        "top_size": "M",
        "bottom_size": "08",
        "shoe_size": "8",
    }

    with _client() as client:
        response = client.patch("/api/v1/profile/body-size", json=payload)

    assert response.status_code == 200
    body = response.json()
    for key, value in payload.items():
        assert body[key] == value


def test_future_birth_date_rejected(mocker, user_a: str) -> None:
    _mock_token_as(mocker, user_a)

    with _client() as client:
        response = client.patch("/api/v1/profile/body-size", json={"birth_date": "2999-01-01"})

    assert response.status_code == 422


def test_notifications_toggle_persists_immediately(mocker, user_a: str) -> None:
    _mock_token_as(mocker, user_a)

    with _client() as client:
        patch_response = client.patch("/api/v1/profile/notifications", json={"notifications_enabled": False})
        get_response = client.get("/api/v1/profile")

    assert patch_response.status_code == 200
    assert patch_response.json()["notifications_enabled"] is False
    assert get_response.json()["notifications_enabled"] is False


def test_two_users_see_only_their_own_profile(mocker, user_a: str, user_b: str) -> None:
    """Route-level proof of SC-004 — the DB/RLS-level proof lives in
    test_user_profile_rls.py; this proves the API itself never crosses users."""
    _mock_token_as(mocker, user_a)
    a_payload = {"style_tags": ["Bold"], "colour_tags": [], "brands_to_avoid": []}
    with _client() as client:
        client.patch("/api/v1/profile/style-preferences", json=a_payload)

    _mock_token_as(mocker, user_b)
    with _client() as client:
        b_response = client.get("/api/v1/profile")

    assert b_response.json()["style_tags"] == []
