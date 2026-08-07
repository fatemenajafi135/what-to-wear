"""Integration test for `GET /api/v1/whoami` (specs/003-auth/contracts/whoami.md).

Unlike test_health.py, this doesn't need a real database or a real Supabase
project — `/whoami` never touches the database, and JWKS verification is
mocked here exactly as it is in tests/unit/test_auth.py. `DATABASE_URL` and
`SUPABASE_URL` still need *some* value so `Settings` can construct during
the app's lifespan startup (`get_engine()` builds an engine lazily; it never
connects for this endpoint), so this test provides fake ones rather than
requiring a running stack.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from whattowear import auth
from whattowear.core.config import get_settings
from whattowear.main import app


@pytest.fixture(autouse=True)
def _fake_settings_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:1/postgres")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_missing_token_rejected() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/whoami")

    assert response.status_code == 401


def test_garbage_token_rejected() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/whoami", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401


def test_valid_token_returns_user_id(mocker) -> None:
    fake_signing_key = mocker.Mock(key="fake-public-key")
    mocker.patch.object(
        auth,
        "_get_jwk_client",
        return_value=mocker.Mock(get_signing_key_from_jwt=mocker.Mock(return_value=fake_signing_key)),
    )
    mocker.patch.object(auth, "jwt_decode", return_value={"sub": "user-123", "aud": "authenticated"})

    with TestClient(app) as client:
        response = client.get("/api/v1/whoami", headers={"Authorization": "Bearer valid.jwt.token"})

    assert response.status_code == 200
    assert response.json() == {"user_id": "user-123"}
