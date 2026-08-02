"""Integration tests for the styling chat + outfit-persistence routes
(specs/008-styling-chat/contracts/recommend.md,
specs/009-suggestion-pager/contracts/recommend.md). Runs against a real
local Supabase database for wardrobe/outfit reads and writes — no mocked
database layer, matching test_closet_routes.py's precedent. The LLM
gateway is never called: `get_compiled_graph` itself is patched at the
route module's own import site
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
from whattowear.schema import CitedSource, Context, DimensionScore, Rationale, ScoredOutfit, SuggestResult

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
        conn.execute(text("DELETE FROM outfits WHERE user_id = :u"), {"u": USER_READY})


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
            context=Context(
                occasion="business casual for a rainy commute", formality="business_casual", condition="rain"
            ),
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
        assert len(body["outfits"]) == 1
        outfit_body = body["outfits"][0]
        returned_ids = {item["id"] for item in outfit_body["items"]}
        assert returned_ids == {ready_closet["top"], ready_closet["bottom"], ready_closet["shoes"]}
        assert outfit_body["match_label"] == "great"
        assert outfit_body["id"] is None  # not saved yet
        assert "[1]" not in outfit_body["rationale_text"]  # no citation markers on the card (§33/§35)
        assert outfit_body["meta_line"] == "business casual for a rainy commute · rain"
        assert "rank_score" not in outfit_body
        assert "citations" not in body  # field removed entirely — no remaining renderer
        assert "score" not in str(body).lower().replace("scores", "")  # no stray numeric score field
        assert body["thread_id"]

    def test_multiple_outfits_returned_in_rank_order_below_floor_dropped(self, ready_closet: dict[str, str]) -> None:
        great = _scored_outfit([ready_closet["top"]], rank_score=0.85, cites=[])
        good = _scored_outfit([ready_closet["bottom"]], rank_score=0.65, cites=[])
        below_floor = _scored_outfit([ready_closet["shoes"]], rank_score=0.2, cites=[])
        result = SuggestResult(outfits=[great, good, below_floor], sources=[])
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"result": result, "note": None}

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                response = client.post("/api/v1/recommend/messages", json={"message": "smart casual"})

        assert response.status_code == 200
        body = response.json()
        assert len(body["outfits"]) == 2  # below_floor dropped entirely, not shown unlabeled
        assert [o["match_label"] for o in body["outfits"]] == ["great", "good"]

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
        assert body["outfits"] == []
        assert body["reply_text"] == "Your closet doesn't have enough items to assemble an outfit for this request."

    def test_all_outfits_below_floor_is_the_empty_case_not_an_error(self, ready_closet: dict[str, str]) -> None:
        below_floor = _scored_outfit([ready_closet["top"]], rank_score=0.1, cites=[])
        result = SuggestResult(outfits=[below_floor], sources=[])
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"result": result, "note": None}

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                response = client.post("/api/v1/recommend/messages", json={"message": "something obscure"})

        assert response.status_code == 200
        body = response.json()
        assert body["outfits"] == []
        assert body["reply_text"]  # generic fallback note, not a fabricated outfit

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


class TestSaveOutfit:
    """specs/009-suggestion-pager/contracts/recommend.md — the pager
    heart's first tap. specs/010-outfits/contracts/recommend-outfits.md —
    the added `thread_id` and server-side citation/dimension-score capture
    (design-decisions.md §38)."""

    def _save_body(self, item_ids: list[str], thread_id: str = "no-such-thread") -> dict:
        return {
            "occasion": "Rainy day commute",
            "meta_line": "Rainy day commute · Business casual",
            "rationale_text": "A cohesive, weather-ready look.",
            "match_label": "great",
            "item_ids": item_ids,
            "thread_id": thread_id,
        }

    def _row(self, outfit_id: str) -> dict:
        with get_engine().begin() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT user_id, occasion, meta_line, rationale_text, match_label, item_ids, favorite, "
                        "title, rationale_with_citations, citations, dimension_scores "
                        "FROM outfits WHERE id = :id"
                    ),
                    {"id": outfit_id},
                )
                .mappings()
                .fetchone()
            )
        assert row is not None
        return dict(row)

    def test_happy_path_creates_a_row_and_returns_favorite_true(self, ready_closet: dict[str, str]) -> None:
        # No matching thread state (a real, never-invoked thread_id) —
        # citations/dimension_scores must degrade to empty, not fail the
        # save (design-decisions.md §38).
        with _client_as(USER_READY) as client:
            response = client.post(
                "/api/v1/recommend/outfits",
                json=self._save_body([ready_closet["top"], ready_closet["bottom"]]),
            )

        assert response.status_code == 201
        body = response.json()
        assert body["favorite"] is True
        assert body["id"]

        # Read the row back directly — a 2xx proves nothing about what was
        # actually stored (handoff §10).
        row = self._row(body["id"])
        assert str(row["user_id"]) == USER_READY
        assert row["occasion"] == "Rainy day commute"
        assert row["meta_line"] == "Rainy day commute · Business casual"
        assert row["rationale_text"] == "A cohesive, weather-ready look."
        assert row["match_label"] == "great"
        assert {str(item_id) for item_id in row["item_ids"]} == {ready_closet["top"], ready_closet["bottom"]}
        assert row["favorite"] is True
        assert row["title"] == "Rainy day commute"  # seeded from occasion (§36)
        assert row["rationale_with_citations"] == ""
        assert row["citations"] == []
        assert row["dimension_scores"] == []

    def test_captures_citations_and_dimension_scores_from_the_threads_last_result(
        self, ready_closet: dict[str, str]
    ) -> None:
        item_ids = [ready_closet["top"], ready_closet["bottom"]]
        outfit = _scored_outfit(item_ids, rank_score=0.85, cites=["rule-1"])
        result = SuggestResult(
            outfits=[outfit],
            sources=[CitedSource(rule_id="rule-1", source="Pair casual denim with a relaxed top.", url="", layer="L3")],
        )
        mock_graph = MagicMock()
        mock_graph.get_state.return_value = MagicMock(values={"user_id": USER_READY, "last_result": result})

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                response = client.post(
                    "/api/v1/recommend/outfits", json=self._save_body(item_ids, thread_id="thread-1")
                )

        assert response.status_code == 201
        row = self._row(response.json()["id"])
        assert row["rationale_with_citations"] == "A clean, casual pairing. [1]"
        assert row["citations"] == [{"number": 1, "text": "Pair casual denim with a relaxed top."}]
        assert row["dimension_scores"] == [
            {"dimension": "color_harmony", "value": 0.8},
            {"dimension": "formality_coherence", "value": 0.8},
            {"dimension": "weather_fitness", "value": 0.8},
            {"dimension": "silhouette_balance", "value": 0.8},
        ]

    def test_degrades_to_empty_when_thread_belongs_to_another_user(self, ready_closet: dict[str, str]) -> None:
        item_ids = [ready_closet["top"]]
        outfit = _scored_outfit(item_ids, rank_score=0.85, cites=["rule-1"])
        result = SuggestResult(
            outfits=[outfit],
            sources=[CitedSource(rule_id="rule-1", source="Some rule.", url="", layer="L3")],
        )
        mock_graph = MagicMock()
        mock_graph.get_state.return_value = MagicMock(values={"user_id": "someone-else", "last_result": result})

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                response = client.post(
                    "/api/v1/recommend/outfits", json=self._save_body(item_ids, thread_id="thread-1")
                )

        assert response.status_code == 201
        row = self._row(response.json()["id"])
        assert row["citations"] == []
        assert row["dimension_scores"] == []

    def test_degrades_to_empty_when_no_outfit_in_last_result_matches_item_ids(
        self, ready_closet: dict[str, str]
    ) -> None:
        other_outfit = _scored_outfit([ready_closet["shoes"]], rank_score=0.85, cites=["rule-1"])
        result = SuggestResult(
            outfits=[other_outfit],
            sources=[CitedSource(rule_id="rule-1", source="Some rule.", url="", layer="L3")],
        )
        mock_graph = MagicMock()
        mock_graph.get_state.return_value = MagicMock(values={"user_id": USER_READY, "last_result": result})

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                response = client.post(
                    "/api/v1/recommend/outfits",
                    json=self._save_body([ready_closet["top"], ready_closet["bottom"]], thread_id="thread-1"),
                )

        assert response.status_code == 201
        row = self._row(response.json()["id"])
        assert row["citations"] == []
        assert row["dimension_scores"] == []

    def test_rejects_an_item_the_caller_does_not_own(self, ready_closet: dict[str, str]) -> None:
        someone_elses_item = str(uuid.uuid4())
        with _client_as(USER_READY) as client:
            response = client.post(
                "/api/v1/recommend/outfits",
                json=self._save_body([ready_closet["top"], someone_elses_item]),
            )

        assert response.status_code == 422
        with get_engine().begin() as conn:
            count = conn.execute(
                text("SELECT count(*) FROM outfits WHERE user_id = :u"), {"u": USER_READY}
            ).scalar_one()
        assert count == 0  # nothing was inserted — validated before, not after, the write

    def test_requires_authentication(self, ready_closet: dict[str, str]) -> None:
        app.dependency_overrides.clear()
        with TestClient(app) as client:
            response = client.post("/api/v1/recommend/outfits", json=self._save_body([ready_closet["top"]]))
        assert response.status_code == 401


class TestToggleOutfitFavorite:
    def test_flips_favorite_and_does_not_delete(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            created = client.post(
                "/api/v1/recommend/outfits",
                json=TestSaveOutfit()._save_body([ready_closet["top"]]),
            )
            outfit_id = created.json()["id"]

            first_toggle = client.post(f"/api/v1/recommend/outfits/{outfit_id}/favorite")
            assert first_toggle.status_code == 200
            assert first_toggle.json()["favorite"] is False

            second_toggle = client.post(f"/api/v1/recommend/outfits/{outfit_id}/favorite")
            assert second_toggle.json()["favorite"] is True

        with get_engine().begin() as conn:
            row = (
                conn.execute(text("SELECT favorite FROM outfits WHERE id = :id"), {"id": outfit_id})
                .mappings()
                .fetchone()
            )
        assert row is not None  # still exists — unsaving toggles, never deletes (design-decisions.md §32)
        assert row["favorite"] is True

    def test_404_for_nonexistent_or_foreign_outfit(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            response = client.post(f"/api/v1/recommend/outfits/{uuid.uuid4()}/favorite")
        assert response.status_code == 404
