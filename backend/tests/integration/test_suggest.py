"""Integration test for POST /suggest (Feature 002 Phase 3, T036).

Same auth-boundary pattern as test_recommend_auth.py: the compiled graph is
mocked (a real call needs the LLM/KB/DB) so this test is about the endpoint
contract — SSE framing, auth gating, and that the response shape matches
contracts/suggest.md — not generation quality (the eval harness's job).
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from whattowear import api
from whattowear.auth import get_current_user_id
from whattowear.schema import Context, DimensionScore, Rationale, ScoredOutfit, SuggestResult


@pytest.fixture
def client(mocker):
    # Feature 005 US3: suggest_endpoint now unconditionally loads the
    # wardrobe and checks the cache before invoking the (mocked) graph —
    # keep this file's original "mocked graph, no DB/Redis dependency"
    # character by mocking those too.
    mocker.patch.object(api, "load_wardrobe", return_value=[])
    mocker.patch.object(api.suggest_cache, "get_cached_result", return_value=None)
    mocker.patch.object(api.suggest_cache, "set_cached_result")
    yield TestClient(api.app)
    api.app.dependency_overrides.pop(get_current_user_id, None)


def _as_user(user_id: str) -> None:
    api.app.dependency_overrides[get_current_user_id] = lambda: user_id


def _scored_outfit(item_id: str, rank_score: float) -> ScoredOutfit:
    return ScoredOutfit(
        items=[item_id],
        rationale=[Rationale(text="goes well together", cites=["L1-x"])],
        scores=[
            DimensionScore(dimension="color_harmony", value=0.8, reason="r"),
            DimensionScore(dimension="formality_coherence", value=0.7, reason="r"),
            DimensionScore(dimension="weather_fitness", value=0.6, reason="r"),
            DimensionScore(dimension="silhouette_balance", value=0.5, reason="r"),
        ],
        rank_score=rank_score,
    )


class _FakeCompiledGraph:
    def __init__(self, final_state):
        self._final_state = final_state
        self.invoked_with = None

    def invoke(self, initial_state, config=None):
        self.invoked_with = initial_state
        return self._final_state


def _final_state(*, user_id, outfits, thread_id="thread-1", note=None):
    ctx = Context(occasion="dinner", formality="casual", user_id=user_id)
    result = SuggestResult(outfits=outfits, sources=[], context=ctx)
    return {"thread_id": thread_id, "result": result, "scored_outfits": outfits, "note": note}


def _extract_events(sse_body: str) -> list[dict]:
    events = []
    for block in sse_body.strip().split("\n\n"):
        lines = block.splitlines()
        event = next(line.removeprefix("event: ") for line in lines if line.startswith("event: "))
        data = next(line.removeprefix("data: ") for line in lines if line.startswith("data: "))
        events.append({"event": event, "data": json.loads(data)})
    return events


def test_missing_bearer_token_rejected(client):
    r = client.post("/suggest", json={"occasion": "dinner"})
    assert r.status_code == 401


def test_graph_driven_by_jwt_sub_not_body_field(client, mocker):
    fake = _FakeCompiledGraph(_final_state(user_id="jwt-user", outfits=[]))
    mocker.patch.object(api, "get_compiled_graph", return_value=fake)
    _as_user("jwt-user")

    client.post("/suggest", json={"occasion": "dinner", "user_id": "victim-uuid"})

    assert fake.invoked_with["user_id"] == "jwt-user"


def test_fresh_request_passes_approach_into_initial_state(client, mocker):
    fake = _FakeCompiledGraph(_final_state(user_id="jwt-user", outfits=[]))
    mocker.patch.object(api, "get_compiled_graph", return_value=fake)
    _as_user("jwt-user")

    client.post("/suggest", json={"occasion": "dinner", "approach": "engine"})

    assert fake.invoked_with["approach"] == "engine"


def test_continuing_request_omits_approach_so_the_checkpoint_wins(client, mocker):
    # Feature 010, research.md Decision 6: a continuing (thread_id supplied)
    # request must NOT re-pass approach, so LangGraph's checkpoint-merge
    # behavior leaves turn 1's persisted value untouched regardless of
    # whatever this turn's body happens to carry.
    fake = _FakeCompiledGraph(_final_state(user_id="jwt-user", outfits=[], thread_id="thread-1"))
    mocker.patch.object(api, "get_compiled_graph", return_value=fake)
    _as_user("jwt-user")

    client.post("/suggest", json={"occasion": "warmer", "thread_id": "thread-1", "approach": "grounded"})

    assert "approach" not in fake.invoked_with


def test_well_stocked_closet_returns_outfits_with_all_four_scores(client, mocker):
    outfits = [_scored_outfit("a", 0.9), _scored_outfit("b", 0.7), _scored_outfit("c", 0.5)]
    fake = _FakeCompiledGraph(_final_state(user_id="jwt-user", outfits=outfits))
    mocker.patch.object(api, "get_compiled_graph", return_value=fake)
    _as_user("jwt-user")

    r = client.post("/suggest", json={"occasion": "dinner"})

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _extract_events(r.text)
    outfit_events = [e for e in events if e["event"] == "outfit"]
    done_events = [e for e in events if e["event"] == "done"]

    assert len(outfit_events) == 3
    assert len(done_events) == 1
    assert len(done_events[0]["data"]["result"]["outfits"]) == 3
    for o in done_events[0]["data"]["result"]["outfits"]:
        assert len(o["scores"]) == 4
        assert {s["dimension"] for s in o["scores"]} == {
            "color_harmony",
            "formality_coherence",
            "weather_fitness",
            "silhouette_balance",
        }


def test_outfits_stream_in_descending_rank_score_order(client, mocker):
    outfits = [_scored_outfit("a", 0.9), _scored_outfit("b", 0.5), _scored_outfit("c", 0.2)]
    fake = _FakeCompiledGraph(_final_state(user_id="jwt-user", outfits=outfits))
    mocker.patch.object(api, "get_compiled_graph", return_value=fake)
    _as_user("jwt-user")

    r = client.post("/suggest", json={"occasion": "dinner"})

    scores = [e["data"]["outfit"]["rank_score"] for e in _extract_events(r.text) if e["event"] == "outfit"]
    assert scores == sorted(scores, reverse=True)


def test_undersized_closet_returns_fewer_outfits_with_note(client, mocker):
    fake = _FakeCompiledGraph(
        _final_state(
            user_id="jwt-user",
            outfits=[_scored_outfit("a", 0.9)],
            note="Only found 1 outfit option(s) — add more items to your closet for more variety.",
        )
    )
    mocker.patch.object(api, "get_compiled_graph", return_value=fake)
    _as_user("jwt-user")

    r = client.post("/suggest", json={"occasion": "dinner"})

    done = next(e for e in _extract_events(r.text) if e["event"] == "done")
    assert len(done["data"]["result"]["outfits"]) == 1
    assert done["data"]["note"] is not None


def test_thread_id_is_echoed_in_done_event(client, mocker):
    fake = _FakeCompiledGraph(_final_state(user_id="jwt-user", outfits=[], thread_id="abc-123"))
    mocker.patch.object(api, "get_compiled_graph", return_value=fake)
    _as_user("jwt-user")

    r = client.post("/suggest", json={"occasion": "dinner"})

    done = next(e for e in _extract_events(r.text) if e["event"] == "done")
    assert done["data"]["thread_id"] == "abc-123"
