"""Integration test for `GET /health` (contracts/health.md under
specs/002-backend-foundation/). Runs against a real local Supabase database —
no mocked database layer (research.md §8). Requires `DATABASE_URL` in the
environment, pointed at a running local Supabase stack (see quickstart.md:
`npx supabase start` from `infra/`).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import whattowear.main as main_module
from whattowear.main import app


def test_health_reports_ok_when_database_reachable() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_reports_unhealthy_when_database_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole reason `/health` reports dependency state instead of just
    returning 200 — contracts/health.md's 503 shape."""
    monkeypatch.setattr(main_module, "_database_reachable", lambda: False)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unhealthy", "failed_dependencies": ["database"]}
