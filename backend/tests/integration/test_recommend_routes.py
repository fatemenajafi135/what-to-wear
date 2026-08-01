"""Integration tests for the styling chat routes (specs/008-styling-chat/
contracts/recommend.md). Runs against a real local Supabase database for
wardrobe reads — no mocked database layer, matching test_closet_routes.py's
precedent. The LLM gateway is never called: `get_compiled_graph` itself is
patched at the route module's own import site
(`whattowear.api.v1.routes.recommend.get_compiled_graph`), the same
"patch where it's imported, not where it's defined" pattern
tests/unit/pipeline/test_engine.py uses for `get_chat_model`.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from whattowear.auth import get_current_access_token, get_current_user_id
from whattowear.core.db import get_engine
from whattowear.main import app
from whattowear.schema import CitedSource, DimensionScore, Rationale, ScoredOutfit, SuggestResult

USER_READY = str(uuid.uuid4())
USER_BLOCKED = str(uuid.uuid4())


def _insert_item(user_id: str, category: str, **overrides: object) -> str:
    item_id = str(uuid.uuid4())
    row = {
        "id": item_id,
        "user_id": user_id,
        "category": category,
        "colors": ["#1b2a4a"],
        "formality": "casual",
        "warmth": 1,
        "season": ["spring"],
        "source": "upload",
        "name": overrides.pop("name", None),
        **overrides,
    }
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO wardrobe_items (id, user_id, category, colors, formality, warmth, season, source, name)"
                " VALUES (:id, :user_id, :category, :colors, :formality, :warmth, :season, :source, :name)"
            ),
            row,
        )
    return item_id


@pytest.fixture
def ready_closet() -> Iterator[dict[str, str]]:
    top = _insert_item(USER_READY, "t-shirt", name="Navy tee")
    bottom = _insert_item(USER_READY, "jeans", name="Blue jeans")
    shoes = _insert_item(USER_READY, "boots", name="Black boots")
    _insert_item(USER_READY, "belt", name="Brown belt")
    _insert_item(USER_READY, "cardigan", name="Grey cardigan")
    yield {"top": top, "bottom": bottom, "shoes": shoes}
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM wardrobe_items WHERE user_id = :u"), {"u": USER_READY})


@pytest.fixture
def blocked_closet() -> Iterator[None]:
    _insert_item(USER_BLOCKED, "t-shirt", name="Only item")
    yield
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM wardrobe_items WHERE user_id = :u"), {"u": USER_BLOCKED})


def _client_as(user_id: str) -> TestClient:
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    app.dependency_overrides[get_current_access_token] = lambda: "fake-access-token"
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def _scored_outfit(items: list[str], rank_score: float, cites: list[str]) -> ScoredOutfit:
    return ScoredOutfit(
        items=items,
        rationale=[Rationale(text="A clean, casual pairing.", cites=cites)],
        scores=[
            DimensionScore(dimension="color_harmony", value=0.8, reason="ok"),
            DimensionScore(dimension="formality_coherence", value=0.8, reason="ok"),
            DimensionScore(dimension="weather_fitness", value=0.8, reason="ok"),
            DimensionScore(dimension="silhouette_balance", value=0.8, reason="ok"),
        ],
        rank_score=rank_score,
    )


class TestReadiness:
    def test_ready_closet(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            response = client.get("/api/v1/recommend/readiness")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is True
        assert body["missing"] == []

    def test_blocked_closet_names_whats_missing(self, blocked_closet: None) -> None:
        with _client_as(USER_BLOCKED) as client:
            response = client.get("/api/v1/recommend/readiness")
        assert response.status_code == 200
        body = response.json()
        assert body["ready"] is False
        assert body["missing"] != []

    def test_missing_token_rejected(self) -> None:
        app.dependency_overrides.clear()
        with TestClient(app) as client:
            response = client.get("/api/v1/recommend/readiness")
        assert response.status_code == 401


class TestSendMessage:
    def test_blocked_closet_is_rejected_and_pipeline_never_invoked(self, blocked_closet: None) -> None:
        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph") as mock_get_graph:
            with _client_as(USER_BLOCKED) as client:
                response = client.post("/api/v1/recommend/messages", json={"message": "business casual"})
            mock_get_graph.assert_not_called()
        assert response.status_code == 403

    def test_happy_path_returns_only_owned_items_and_no_numbers(self, ready_closet: dict[str, str]) -> None:
        outfit = _scored_outfit(
            [ready_closet["top"], ready_closet["bottom"], ready_closet["shoes"]],
            rank_score=0.85,
            cites=["rule-1"],
        )
        result = SuggestResult(
            outfits=[outfit],
            sources=[CitedSource(rule_id="rule-1", source="Pair casual denim with a relaxed top.", url="", layer="L3")],
        )
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"result": result, "note": None}

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                response = client.post(
                    "/api/v1/recommend/messages", json={"message": "business casual for a rainy commute"}
                )

        assert response.status_code == 200
        body = response.json()
        assert body["outfit"] is not None
        returned_ids = {item["id"] for item in body["outfit"]["items"]}
        assert returned_ids == {ready_closet["top"], ready_closet["bottom"], ready_closet["shoes"]}
        assert body["outfit"]["match_label"] == "great"
        assert len(body["citations"]) == 1
        assert body["citations"][0]["number"] == 1
        assert "rank_score" not in body["outfit"]
        assert "score" not in str(body).lower().replace("scores", "")  # no stray numeric score field
        assert body["thread_id"]

    def test_zero_outfits_returns_honest_note_no_fabricated_outfit(self, ready_closet: dict[str, str]) -> None:
        result = SuggestResult(outfits=[], sources=[])
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {
            "result": result,
            "note": "Your closet doesn't have enough items to assemble an outfit for this request.",
        }

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                response = client.post("/api/v1/recommend/messages", json={"message": "black tie gala"})

        assert response.status_code == 200
        body = response.json()
        assert body["outfit"] is None
        assert body["citations"] == []
        assert body["reply_text"] == "Your closet doesn't have enough items to assemble an outfit for this request."

    def test_backstop_timeout_returns_504(self, ready_closet: dict[str, str]) -> None:
        import time

        def _slow_invoke(*_args: object, **_kwargs: object) -> dict:
            time.sleep(0.2)
            return {"result": SuggestResult(outfits=[]), "note": None}

        mock_graph = MagicMock()
        mock_graph.invoke.side_effect = _slow_invoke

        with (
            patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph),
            patch("whattowear.api.v1.routes.recommend.get_settings") as mock_settings,
        ):
            mock_settings.return_value.wtw_wardrobe_min_items = 5
            mock_settings.return_value.wtw_wardrobe_sparse_threshold = 15
            mock_settings.return_value.wtw_styling_request_timeout_seconds = 0.01
            with _client_as(USER_READY) as client:
                response = client.post("/api/v1/recommend/messages", json={"message": "business casual"})

        assert response.status_code == 504

    def test_empty_message_rejected(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            response = client.post("/api/v1/recommend/messages", json={"message": "   "})
        assert response.status_code == 422

    def test_refinement_echoes_thread_id_from_first_response(self, ready_closet: dict[str, str]) -> None:
        """The route's own responsibility — not re-testing the pipeline's
        internal refinement parsing (unmodified, already evaluated elsewhere,
        constitution Principle I) — is that a `thread_id` is minted once and
        then correctly threaded through on every subsequent call."""
        outfit = _scored_outfit([ready_closet["top"]], rank_score=0.85, cites=[])
        result = SuggestResult(outfits=[outfit], sources=[])
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"result": result, "note": None}

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                first = client.post("/api/v1/recommend/messages", json={"message": "business casual"})
                thread_id = first.json()["thread_id"]

                second = client.post(
                    "/api/v1/recommend/messages",
                    json={"message": "something warmer", "thread_id": thread_id},
                )

        assert second.status_code == 200
        assert second.json()["thread_id"] == thread_id
        second_call_config = mock_graph.invoke.call_args_list[1].kwargs["config"]
        assert second_call_config == {"configurable": {"thread_id": thread_id}}
        second_call_input = mock_graph.invoke.call_args_list[1].args[0]
        assert second_call_input["thread_id"] == thread_id
