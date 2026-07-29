"""Integration test for `GET /health` (contracts/health.md under
specs/002-backend-foundation/). Runs against a real local Supabase database —
no mocked database layer (research.md §8). Requires `DATABASE_URL` in the
environment, pointed at a running local Supabase stack (see quickstart.md:
`npx supabase start` from `infra/`).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from whattowear.main import app


def test_health_reports_ok_when_database_reachable() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
