"""Integration test for the /recommend auth gate (Feature 002 Phase 1).

Closes the pre-002 cross-user leak: /recommend used to take a free-form
`user_id` in the request body with no JWT check, so anyone could read any
user's closet through the pipeline. It must now (1) reject an unauthenticated
call with 401 and (2) drive the pipeline with the verified JWT `sub`, never a
body-supplied id.

The pipeline itself (KB/retrieval/LLM) is mocked — this test is about the auth
boundary, not generation quality (that's the eval harness's job).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from whattowear import api
from whattowear.auth import get_current_user_id
from whattowear.schema import OutfitResult


@pytest.fixture
def client():
    yield TestClient(api.app)
    api.app.dependency_overrides.pop(get_current_user_id, None)


def _as_user(user_id: str) -> None:
    api.app.dependency_overrides[get_current_user_id] = lambda: user_id


def test_missing_bearer_token_rejected(client):
    r = client.post("/recommend", json={"occasion": "dinner"})
    assert r.status_code == 401


def test_pipeline_driven_by_jwt_sub_not_body_user_id(client, mocker):
    captured = {}

    def fake_run_pipeline(occasion, **kwargs):
        captured["occasion"] = occasion
        captured["user_id"] = kwargs.get("user_id")
        return SimpleNamespace(result=OutfitResult(outfits=[]))

    mocker.patch.object(api, "run_pipeline", side_effect=fake_run_pipeline)
    _as_user("jwt-user")

    # a malicious body tries to smuggle someone else's id; it must be ignored
    r = client.post("/recommend", json={"occasion": "dinner", "user_id": "victim-uuid"})

    assert r.status_code == 200
    assert captured["occasion"] == "dinner"
    assert captured["user_id"] == "jwt-user"
