"""Regression test for a real bug caught during feature 004's manual browser
verification: without CORS middleware, every request from the Next.js dev
server was silently blocked by the browser's preflight check before it ever
reached a route — `curl`/pytest's `TestClient` never surfaces this, since
neither goes through a browser's CORS enforcement, which is exactly why it
went unnoticed until an actual browser was used against the API for the
first time (feature 003's `/whoami` was never called from the UI).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

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
