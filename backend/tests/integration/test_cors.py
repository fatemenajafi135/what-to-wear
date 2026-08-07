"""Regression test for a real bug caught during feature 004's manual browser
verification: without CORS middleware, every request from the Next.js dev
server was silently blocked by the browser's preflight check before it ever
reached a route — `curl`/pytest's `TestClient` never surfaces this, since
neither goes through a browser's CORS enforcement, which is exactly why it
went unnoticed until an actual browser was used against the API for the
first time (feature 003's `/whoami` was never called from the UI).
"""

from __future__ import annotations

import importlib

import httpx
import pytest
from fastapi.testclient import TestClient

import whattowear.main
from whattowear.core.config import DEFAULT_CORS_ORIGINS, parse_cors_origins
from whattowear.main import app


def test_preflight_allows_the_frontend_dev_origin() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/closet/items",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_preflight_allows_the_e2e_test_origin() -> None:
    """frontend/playwright.config.ts runs its own `next dev` on port 3100 so
    the e2e suite never collides with a developer's own running dev server —
    a second real origin that must also be allowed."""
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/closet/items",
            headers={"Origin": "http://localhost:3100", "Access-Control-Request-Method": "GET"},
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3100"


def test_preflight_rejects_an_unlisted_origin() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/closet/items",
            headers={"Origin": "http://evil.example.com", "Access-Control-Request-Method": "GET"},
        )
    assert "access-control-allow-origin" not in response.headers


def _preflight(client: TestClient, origin: str) -> httpx.Response:
    return client.options(
        "/api/v1/closet/items",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )


def test_a_configured_deployment_origin_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The regression guard for feature 017.

    `WTW_CORS_ORIGINS` was briefly added to `Settings` — with its own passing
    unit tests — while `main.py` still hardcoded the localhost list, so the
    variable, its tests and `render.yaml`'s entry were all inert and a deployed
    frontend would have had every request rejected by CORS. Nothing caught it:
    the unit tests exercised the parser in isolation, and every test in this
    file only ever used a localhost origin, which is allowed either way. This
    asserts the wiring itself — that a configured origin reaches the running
    app, and that configuring one replaces the defaults rather than adding to
    them.

    `importlib.reload` because `main` reads the environment once, at import,
    when it registers `CORSMiddleware`. Safe here: pytest imports every test
    module at collection time, so any other module's `from whattowear.main
    import app` is already bound to the original object, and the module is
    reloaded again on the way out.

    No `with TestClient(...)`: a CORS preflight is answered by middleware
    before routing, so this needs no database and stays runnable when one
    isn't configured.
    """
    deployed = "https://w2w-staging.vercel.app"
    monkeypatch.setenv("WTW_CORS_ORIGINS", f"{deployed}, https://second.example.com")
    reloaded = importlib.reload(whattowear.main)
    try:
        client = TestClient(reloaded.app)

        allowed = _preflight(client, deployed)
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == deployed

        # The second entry follows a comma-SPACE. Unstripped it would be
        # " https://second.example.com", which never matches a browser's
        # `Origin` header — and fails silently, with no error anywhere.
        spaced = _preflight(client, "https://second.example.com")
        assert spaced.status_code == 200
        assert spaced.headers["access-control-allow-origin"] == "https://second.example.com"

        # Configuring origins REPLACES the local defaults; it does not extend
        # them. A deployed backend should not still be answering localhost.
        assert "access-control-allow-origin" not in _preflight(client, "http://localhost:3000").headers
    finally:
        monkeypatch.delenv("WTW_CORS_ORIGINS", raising=False)
        importlib.reload(whattowear.main)


def test_defaults_still_apply_when_the_variable_is_unset() -> None:
    """The other half of the wiring: reading the env must not have broken the
    no-configuration path that every local dev and the e2e suites rely on."""
    assert parse_cors_origins(None) == DEFAULT_CORS_ORIGINS
    assert "http://localhost:3000" in DEFAULT_CORS_ORIGINS
    assert "http://127.0.0.1:3000" in DEFAULT_CORS_ORIGINS
