"""Integration test for conversational refinement (Feature 002 Phase 4, T045).

Unlike test_suggest.py (which mocks the compiled graph to test the endpoint
contract in isolation), this exercises the REAL graph across two turns on
the same thread — refinement only means something if `wardrobe_retrieval`'s
delta-shifted pruning and the checkpointer's cross-turn state persistence
are both real, not mocked. Needs the LLM/KB/DB, like eval/harness.py; also
inherits its documented flakiness under transient network drops.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from whattowear import api
from whattowear.auth import get_current_user_id
from whattowear.crud import EVAL_BASELINE_USER_ID
from whattowear.schema import FORMALITY_ORDER


@pytest.fixture
def client():
    api.app.dependency_overrides[get_current_user_id] = lambda: str(EVAL_BASELINE_USER_ID)
    yield TestClient(api.app)
    api.app.dependency_overrides.pop(get_current_user_id, None)


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


def _wardrobe_by_id(client: TestClient) -> dict:
    r = client.get("/wardrobe/items")
    assert r.status_code == 200
    return {it["id"]: it for it in r.json()}


def _mean_warmth(payload: dict, wardrobe: dict) -> float:
    """Feature 007 Task C: the "warmer" floor is now per-category-relative
    (graph.py's _category_warmth_ceiling), not a blanket footwear/accessory
    exemption — every group now has a real, if sometimes small, floor, so
    every group's warmth belongs in this mean instead of being excluded."""
    warmths = [wardrobe[i]["warmth"] for o in payload["result"]["outfits"] for i in o["items"] if i in wardrobe]
    return sum(warmths) / len(warmths) if warmths else 0.0


def _max_formality_notch(payload: dict, wardrobe: dict) -> int:
    notches = [
        FORMALITY_ORDER[wardrobe[i]["formality"]]
        for o in payload["result"]["outfits"]
        for i in o["items"]
        if i in wardrobe
    ]
    return max(notches) if notches else 0


def _item_sets(payload: dict) -> set[frozenset]:
    return {frozenset(o["items"]) for o in payload["result"]["outfits"]}


def _is_fallback(payload: dict) -> bool:
    """FR-015: a refinement whose tightened bounds left nothing generated
    falls back to the previous result with an explanatory note — a
    legitimate outcome, not a bug, so the quantitative checks below don't
    apply to it (this is what a too-small/undiverse closet looks like)."""
    return bool(payload.get("note")) and "previous suggestions" in payload["note"]


class TestWarmerRefinement:
    """US4 Acceptance Scenario 1, SC-007."""

    def test_warmer_raises_mean_warmth_and_preserves_occasion(self, client):
        wardrobe = _wardrobe_by_id(client)

        # No temp_c: context_assembler falls back to deriving `season` from
        # the current calendar month when temp_c is given without a
        # location (pre-existing Phase 1 behavior, out of scope here) --
        # in summer that excludes the closet's autumn/winter-tagged warm
        # layers regardless of the warmer delta's own warmth floor, which
        # would make this test's fallback trigger for an unrelated reason.
        first = _suggest(client, occasion="office")
        second = _suggest(client, occasion="warmer", thread_id=first["thread_id"])

        assert second["result"]["context"]["occasion"] == "office"
        if _is_fallback(second):
            pytest.skip("refinement fell back to the previous result (FR-015) — nothing to compare")
        if first["result"]["outfits"] and second["result"]["outfits"]:
            # SC-007's "+1 mean warmth" bar is an aggregate stated over "at
            # least 90% of cases" -- a population statistic, not a
            # per-invocation guarantee a single LLM-sampled run can prove
            # either way. What this run DOES verify deterministically is the
            # mechanism itself (unit-tested precisely in test_graph.py); here
            # we confirm it produces a clear, meaningful increase in practice.
            assert _mean_warmth(second, wardrobe) > _mean_warmth(first, wardrobe) + 0.5


class TestLessFormalRefinement:
    """US4 Acceptance Scenario 2, SC-007."""

    def test_less_formal_lowers_formality_and_preserves_occasion(self, client):
        wardrobe = _wardrobe_by_id(client)

        first = _suggest(client, occasion="office", formality="business_casual", temp_c=15)
        second = _suggest(client, occasion="less formal", thread_id=first["thread_id"])

        assert second["result"]["context"]["occasion"] == "office"
        if _is_fallback(second):
            pytest.skip("refinement fell back to the previous result (FR-015) — nothing to compare")
        if first["result"]["outfits"] and second["result"]["outfits"]:
            # the acceptable formality ceiling shifted down by a notch (FR-013's
            # actual mechanism) -- verified directly rather than via a raw mean
            # delta, which is sensitive to what the LLM happened to pick on
            # turn 1 within its own (wider) allowed band.
            original_notch = FORMALITY_ORDER["business_casual"]
            assert _max_formality_notch(second, wardrobe) < original_notch


class TestAlternativesRefinement:
    """US4 Acceptance Scenario 3."""

    def test_alternatives_returns_a_different_outfit_set(self, client):
        first = _suggest(client, occasion="office", temp_c=15)
        second = _suggest(client, occasion="give me alternatives", thread_id=first["thread_id"])

        assert second["result"]["context"]["occasion"] == "office"
        if first["result"]["outfits"] and second["result"]["outfits"]:
            assert _item_sets(second) != _item_sets(first)
