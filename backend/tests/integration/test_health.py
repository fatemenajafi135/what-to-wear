"""Integration test for GET /health (Feature 005, FR-012).

A `/speckit.analyze` finding: the spec's own Edge Case ("backend can't reach
the database or vector store... surfaced as a clear health-check failure")
had no FR/task until this feature closed it. `_db_reachable`/
`_vector_store_reachable` are mocked here (they hit the real DB/Qdrant
directly, not through a FastAPI dependency) — this test is about the
endpoint's status-code/body contract, not connectivity itself (which is
already exercised for real by every other test in this suite that needs a
live DB).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from whattowear import api


def test_healthy_when_both_dependencies_reachable(mocker):
    mocker.patch.object(api, "_db_reachable", return_value=True)
    mocker.patch.object(api, "_vector_store_reachable", return_value=True)
    client = TestClient(api.app)

    r = client.get("/health")

    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_unhealthy_when_database_unreachable(mocker):
    mocker.patch.object(api, "_db_reachable", return_value=False)
    mocker.patch.object(api, "_vector_store_reachable", return_value=True)
    client = TestClient(api.app)

    r = client.get("/health")

    assert r.status_code == 503
    assert r.json() == {"status": "unhealthy", "failed_dependencies": ["database"]}


def test_unhealthy_when_vector_store_unreachable(mocker):
    mocker.patch.object(api, "_db_reachable", return_value=True)
    mocker.patch.object(api, "_vector_store_reachable", return_value=False)
    client = TestClient(api.app)

    r = client.get("/health")

    assert r.status_code == 503
    assert r.json()["failed_dependencies"] == ["vector_store"]


def test_real_dependencies_reachable_in_this_dev_environment():
    """Not mocked -- confirms the real probes work against this session's
    actual configured DB/Qdrant, not just that the endpoint wires mocks
    correctly above."""
    client = TestClient(api.app)

    r = client.get("/health")

    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
