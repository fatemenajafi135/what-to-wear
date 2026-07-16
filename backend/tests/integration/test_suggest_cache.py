"""Integration test for the per-user /suggest cache (Feature 005 US3/FR-006/007).

Uses the real compiled graph (like test_suggest_refinement.py) against the
seeded eval-baseline closet, and a real (local) Redis instance — no mocking
of the cache itself. `get_compiled_graph` is wrapped in a `Mock` (still
returning the real compiled graph) purely so call counts prove whether the
graph ran, without relying on timing.
"""

from __future__ import annotations

import json
import os

import pytest
import redis as redis_lib
from fastapi.testclient import TestClient

from whattowear import api
from whattowear.auth import get_current_user_id
from whattowear.crud import EVAL_BASELINE_USER_ID
from whattowear.pipeline import graph as graph_module


@pytest.fixture(autouse=True)
def _clean_cache():
    """Every test in this file uses the same `occasion="office"` against the
    same `EVAL_BASELINE_USER_ID`, so a cache entry written by one test would
    otherwise leak into the next (Redis isn't rolled back the way the DB
    fixture is) — flush before each test for isolation."""
    client = redis_lib.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    client.flushdb()
    yield
    client.flushdb()


@pytest.fixture
def client():
    api.app.dependency_overrides[get_current_user_id] = lambda: str(EVAL_BASELINE_USER_ID)
    yield TestClient(api.app)
    api.app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture
def graph_call_spy(mocker):
    """Spies on `graph.invoke` — the expensive retrieval+generation+LLM
    path — not `get_compiled_graph()` itself. A cache hit legitimately still
    calls `get_compiled_graph()` once (to call `update_state` and seed the
    checkpointer for a possible later refinement, api.py's own docstring),
    it just must never call `invoke`."""
    real_graph = graph_module.get_compiled_graph()
    return mocker.patch.object(real_graph, "invoke", wraps=real_graph.invoke)


def _suggest(client: TestClient, **body) -> dict:
    r = client.post("/suggest", json=body)
    assert r.status_code == 200
    done = None
    for block in r.text.strip().split("\n\n"):
        lines = block.splitlines()
        event = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
        data = next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
        if event == "done":
            done = json.loads(data)
    assert done is not None, "stream ended without a done event"
    return done


def _first_item_id(client: TestClient) -> str:
    r = client.get("/wardrobe/items")
    assert r.status_code == 200
    return r.json()[0]["id"]


def test_repeated_fresh_request_hits_cache_and_skips_the_graph(client, graph_call_spy):
    first = _suggest(client, occasion="office")
    assert graph_call_spy.call_count == 1

    second = _suggest(client, occasion="office")

    assert graph_call_spy.call_count == 1, "cache hit must not invoke the graph again"
    assert second["result"] == first["result"]


def test_closet_edit_invalidates_the_cache(client, graph_call_spy):
    _suggest(client, occasion="office")
    assert graph_call_spy.call_count == 1

    item_id = _first_item_id(client)
    r = client.patch(f"/wardrobe/items/{item_id}", json={"pattern": "a-new-pattern-marking-an-edit"})
    assert r.status_code == 200

    _suggest(client, occasion="office")

    assert graph_call_spy.call_count == 2, "an edited closet must miss the stale cache entry"


def test_a_thread_id_continuing_a_conversation_is_never_cached(client, graph_call_spy):
    first = _suggest(client, occasion="office")
    thread_id = first["thread_id"]

    _suggest(client, occasion="warmer", thread_id=thread_id)

    assert graph_call_spy.call_count == 2, "a refinement turn must always run the graph, never the cache"


def test_redis_unreachable_degrades_to_processing_fresh(client, mocker):
    from whattowear.pipeline import cache as suggest_cache

    unreachable_client = redis_lib.Redis(host="localhost", port=1, socket_connect_timeout=0.2, socket_timeout=0.2)
    mocker.patch.object(suggest_cache, "_get_client", return_value=unreachable_client)

    result = _suggest(client, occasion="office")

    assert result["result"]["outfits"] is not None
