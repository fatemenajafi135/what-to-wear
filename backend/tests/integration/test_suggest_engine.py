"""Integration tests for approach="engine" (Feature 010, WP2 Engine).

T008/T016 [US1/US2]: exercises the REAL graph through style_retrieval (live
KB/Qdrant/Cohere) and wardrobe_retrieval/engine_enumerate_and_score (pure
Python) — only the wardrobe (mocked, synthetic) and the engine_write LLM
call are controlled, proving enumerate+score+select is genuinely wired
end-to-end, not just at the unit level. Needs the LLM gateway/KB/DB, like
test_suggest_refinement.py; inherits its documented flakiness under
transient network drops (CLAUDE.md).
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from whattowear import api
from whattowear.auth import get_current_user_id
from whattowear.pipeline import engine as engine_module
from whattowear.pipeline.generator import GenRationale
from whattowear.schema import WardrobeItem

_TEST_USER_ID = str(uuid.uuid4())


def _item(id, category, *, formality="business_casual", warmth=2, colors=None) -> WardrobeItem:
    return WardrobeItem(
        id=id,
        category=category,
        colors=colors or ["#1b2a4a"],
        formality=formality,
        warmth=warmth,
        season=["spring", "summer", "autumn", "winter"],
    )


# A "perfect" neutral, formality-exact combo vs. a clashing, one-notch-off
# combo — gives the deterministic scorer a genuine reason to rank the
# perfect combo first (color_harmony + formality_coherence both favor it).
_PERFECT = [
    _item("top-perfect", "dress_shirt", colors=["#1b2a4a"]),  # navy
    _item("bottom-perfect", "trousers", colors=["#36454f"]),  # charcoal
    _item("shoe-perfect", "loafers", colors=["#36454f"]),
]
_CLASHING = [
    _item("top-clash", "t-shirt", formality="smart_casual", colors=["#ff6347"]),  # tomato
    _item("bottom-clash", "jeans", formality="smart_casual", colors=["#50c878"]),  # emerald
    _item("shoe-clash", "sneakers", formality="smart_casual", colors=["#0000ff"]),  # blue
]
_WARDROBE = _PERFECT + _CLASHING


def _valid_selection_output(count: int) -> "engine_module.EngineWriteOutput":
    return engine_module.EngineWriteOutput(
        selections=[
            engine_module.EngineSelection(index=i, rationale=[GenRationale(text=f"pick {i}", cites=[])])
            for i in range(count)
        ]
    )


@pytest.fixture
def client():
    api.app.dependency_overrides[get_current_user_id] = lambda: _TEST_USER_ID
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


class TestEngineHappyPath:
    def test_engine_approach_returns_3_outfits_traceable_to_real_combos(self, client, mocker):
        mocker.patch.object(api, "load_wardrobe", return_value=_WARDROBE)
        shortlist_spy = mocker.spy(engine_module, "_format_shortlist")
        fake_llm = mocker.Mock()
        fake_llm.with_structured_output.return_value.invoke.return_value = _valid_selection_output(3)
        mocker.patch.object(engine_module, "get_chat_model", return_value=fake_llm)

        payload = _suggest(client, occasion="office", approach="engine")

        outfits = payload["result"]["outfits"]
        assert len(outfits) == 3
        wardrobe_ids = {it.id for it in _WARDROBE}
        for outfit in outfits:
            assert set(outfit["items"]) <= wardrobe_ids  # every item genuinely owned
            assert len(outfit["scores"]) == 4  # same ScoredOutfit shape as the default path

        # The perfect combo ranked first in the shortlist offered to the LLM.
        shortlist = shortlist_spy.call_args[0][0]
        assert set(shortlist[0].items) == {"top-perfect", "bottom-perfect", "shoe-perfect"}

    def test_default_approach_never_touches_the_engine_llm_call(self, client, mocker):
        mocker.patch.object(api, "load_wardrobe", return_value=_WARDROBE)
        get_chat_model_spy = mocker.spy(engine_module, "get_chat_model")

        payload = _suggest(client, occasion="office")  # approach omitted -> grounded path

        assert "outfits" in payload["result"]
        assert get_chat_model_spy.call_count == 0


class TestEngineMalformedSelectionFallback:
    def test_out_of_range_selection_still_returns_3_valid_grounded_outfits(self, client, mocker):
        mocker.patch.object(api, "load_wardrobe", return_value=_WARDROBE)
        fake_llm = mocker.Mock()
        malformed = engine_module.EngineWriteOutput(
            selections=[
                engine_module.EngineSelection(index=0, rationale=[]),
                engine_module.EngineSelection(index=1, rationale=[]),
                engine_module.EngineSelection(index=999, rationale=[]),  # out of range
            ]
        )
        fake_llm.with_structured_output.return_value.invoke.return_value = malformed
        mocker.patch.object(engine_module, "get_chat_model", return_value=fake_llm)

        payload = _suggest(client, occasion="office", approach="engine")

        outfits = payload["result"]["outfits"]
        assert len(outfits) == 3
        wardrobe_ids = {it.id for it in _WARDROBE}
        for outfit in outfits:
            assert set(outfit["items"]) <= wardrobe_ids
            for r in outfit["rationale"]:
                assert r["cites"] == []  # deterministic fallback never fabricates a citation
