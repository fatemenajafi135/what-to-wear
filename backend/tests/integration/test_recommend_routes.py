"""Integration tests for the styling chat + outfit-persistence routes
(specs/008-styling-chat/contracts/recommend.md,
specs/009-suggestion-pager/contracts/recommend.md,
specs/010-outfits/contracts/recommend-outfits.md). Runs against a real
local Supabase database for wardrobe/outfit reads and writes — no mocked
database layer, matching test_closet_routes.py's precedent. The LLM
gateway is never called: `get_compiled_graph` itself is patched at the
route module's own import site
(`whattowear.api.v1.routes.recommend.get_compiled_graph`), the same
"patch where it's imported, not where it's defined" pattern
tests/unit/pipeline/test_engine.py uses for `get_chat_model`.

design-decisions.md §42: there is no standalone "save" endpoint anymore —
every outfit `POST /recommend/messages` returns is already persisted by
the time the response is sent. `_generate_outfit` below is therefore the
one seeding helper every other route's tests use to get a real saved
outfit into the database: it mocks the pipeline call (never the
persistence), so every resulting row goes through the real `send_message`
code path, same as a real user's request would.
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


def _generate_outfit(
    client: TestClient,
    item_ids: list[str],
    occasion: str = "Rainy day commute",
    cites: list[str] | None = None,
    sources: list[CitedSource] | None = None,
) -> dict:
    """The one way a saved outfit comes into existence now (design-
    decisions.md §42) — mocks the pipeline's own `graph.invoke`, not
    persistence, so the resulting row goes through the real
    `send_message`/`SupabaseOutfitRepository.create` path. Returns the
    generated `StylingOutfit` dict (already carrying a real `id`)."""
    outfit = _scored_outfit(item_ids, rank_score=0.85, cites=cites or [])
    result = SuggestResult(outfits=[outfit], sources=sources or [])
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {"result": result, "note": None}
    with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
        response = client.post("/api/v1/recommend/messages", json={"message": occasion})
    assert response.status_code == 200
    outfits = response.json()["outfits"]
    assert len(outfits) == 1
    return outfits[0]


def _outfit_row(outfit_id: str) -> dict:
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
    """specs/009-suggestion-pager/contracts/recommend.md, extended by
    design-decisions.md §42: every outfit this route returns is already
    persisted (favorited by default) by the time the response is sent —
    verified below by reading the row back, not just checking the 2xx."""

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
        assert outfit_body["id"]  # already saved (design-decisions.md §42) — never null now
        assert outfit_body["favorite"] is True  # favorited by default
        assert "[1]" not in outfit_body["rationale_text"]  # no citation markers on the card (§33/§35)
        assert outfit_body["meta_line"] == "business casual for a rainy commute · rain"
        assert "rank_score" not in outfit_body
        assert "citations" not in outfit_body  # not on the card shape — only on the stored row (§38/§42)
        assert body["thread_id"]

        # Read the row back directly — a 2xx proves nothing about what was
        # actually stored (handoff §10).
        row = _outfit_row(outfit_body["id"])
        assert str(row["user_id"]) == USER_READY
        assert row["favorite"] is True
        assert row["title"] == "business casual for a rainy commute"  # seeded from occasion (§36)
        assert row["rationale_with_citations"] == "A clean, casual pairing. [1]"
        assert row["citations"] == [{"number": 1, "text": "Pair casual denim with a relaxed top."}]
        assert row["dimension_scores"] == [
            {"dimension": "color_harmony", "value": 0.8},
            {"dimension": "formality_coherence", "value": 0.8},
            {"dimension": "weather_fitness", "value": 0.8},
            {"dimension": "silhouette_balance", "value": 0.8},
        ]

    def test_multiple_outfits_returned_in_rank_order_below_floor_dropped_and_all_saved(
        self, ready_closet: dict[str, str]
    ) -> None:
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
        assert len(body["outfits"]) == 2  # below_floor dropped entirely, not shown or saved
        assert [o["match_label"] for o in body["outfits"]] == ["great", "good"]
        assert all(o["id"] for o in body["outfits"])

        with get_engine().begin() as conn:
            count = conn.execute(
                text("SELECT count(*) FROM outfits WHERE user_id = :u"), {"u": USER_READY}
            ).scalar_one()
        assert count == 2  # exactly the two surfaced outfits — the below-floor one was never persisted

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

    def test_outfit_including_a_catalog_item_persists_only_the_owned_ones(self, ready_closet: dict[str, str]) -> None:
        """A scored outfit may legitimately include a shared-catalog item
        (Constitution IV) — `_resolve_outfit` already drops it from what's
        shown since it isn't in the caller's own wardrobe; the persisted row
        must match what was shown, not the pipeline's raw item list."""
        catalog_item_id = str(uuid.uuid4())
        outfit = _scored_outfit([ready_closet["top"], catalog_item_id], rank_score=0.85, cites=[])
        result = SuggestResult(outfits=[outfit], sources=[])
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"result": result, "note": None}

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                response = client.post("/api/v1/recommend/messages", json={"message": "smart casual"})

        outfit_body = response.json()["outfits"][0]
        assert {item["id"] for item in outfit_body["items"]} == {ready_closet["top"]}
        row = _outfit_row(outfit_body["id"])
        assert {str(item_id) for item_id in row["item_ids"]} == {ready_closet["top"]}


class TestListOutfits:
    """specs/010-outfits/contracts/recommend-outfits.md — the Outfits
    gallery."""

    def test_returns_only_the_callers_outfits_newest_first(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            first_id = _generate_outfit(client, [ready_closet["top"]], occasion="First")["id"]
            second_id = _generate_outfit(client, [ready_closet["bottom"]], occasion="Second")["id"]

            response = client.get("/api/v1/recommend/outfits")

        assert response.status_code == 200
        body = response.json()
        assert [o["id"] for o in body["outfits"]] == [second_id, first_id]
        assert [o["title"] for o in body["outfits"]] == ["Second", "First"]

    def test_item_count_and_thumbnail_truncation_at_four(self, ready_closet: dict[str, str]) -> None:
        five_items = [
            ready_closet["top"],
            ready_closet["bottom"],
            ready_closet["shoes"],
            _insert_item(USER_READY, "belt", name="Second belt"),
            _insert_item(USER_READY, "cardigan", name="Second cardigan"),
        ]
        with _client_as(USER_READY) as client:
            _generate_outfit(client, five_items)
            response = client.get("/api/v1/recommend/outfits")

        assert response.status_code == 200
        outfit = response.json()["outfits"][0]
        assert outfit["item_count"] == 5
        assert len(outfit["item_thumbnails"]) == 4  # never more than 4 real thumbnails

    def test_empty_list_for_a_user_with_no_saved_outfits(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            response = client.get("/api/v1/recommend/outfits")

        assert response.status_code == 200
        assert response.json()["outfits"] == []

    def test_does_not_return_another_users_outfits(self, ready_closet: dict[str, str], blocked_closet: None) -> None:
        with _client_as(USER_READY) as client:
            _generate_outfit(client, [ready_closet["top"]])

        with _client_as(USER_BLOCKED) as client:
            response = client.get("/api/v1/recommend/outfits")

        assert response.status_code == 200
        assert response.json()["outfits"] == []

    def test_requires_authentication(self, ready_closet: dict[str, str]) -> None:
        app.dependency_overrides.clear()
        with TestClient(app) as client:
            response = client.get("/api/v1/recommend/outfits")
        assert response.status_code == 401


class TestGetOutfit:
    """specs/010-outfits/contracts/recommend-outfits.md — Outfit detail."""

    def test_happy_path_returns_full_detail(self, ready_closet: dict[str, str]) -> None:
        item_ids = [ready_closet["top"], ready_closet["bottom"]]
        with _client_as(USER_READY) as client:
            created = _generate_outfit(
                client,
                item_ids,
                cites=["rule-1"],
                sources=[
                    CitedSource(rule_id="rule-1", source="Pair casual denim with a relaxed top.", url="", layer="L3")
                ],
            )
            response = client.get(f"/api/v1/recommend/outfits/{created['id']}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == created["id"]
        assert {item["id"] for item in body["items"]} == set(item_ids)
        assert body["rationale_with_citations"] == "A clean, casual pairing. [1]"
        assert body["citations"] == [{"number": 1, "text": "Pair casual denim with a relaxed top."}]
        assert body["dimension_scores"] == [
            {"dimension": "color_harmony", "value": 0.8},
            {"dimension": "formality_coherence", "value": 0.8},
            {"dimension": "weather_fitness", "value": 0.8},
            {"dimension": "silhouette_balance", "value": 0.8},
        ]

    def test_omits_an_item_no_longer_owned(self, ready_closet: dict[str, str]) -> None:
        removable = _insert_item(USER_READY, "belt", name="Removable belt")
        with _client_as(USER_READY) as client:
            created = _generate_outfit(client, [ready_closet["top"], removable])

            with get_engine().begin() as conn:
                conn.execute(text("DELETE FROM wardrobe_items WHERE id = :id"), {"id": removable})

            response = client.get(f"/api/v1/recommend/outfits/{created['id']}")

        assert response.status_code == 200
        assert {item["id"] for item in response.json()["items"]} == {ready_closet["top"]}

    def test_404_for_nonexistent_or_foreign_outfit(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            response = client.get(f"/api/v1/recommend/outfits/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_requires_authentication(self, ready_closet: dict[str, str]) -> None:
        app.dependency_overrides.clear()
        with TestClient(app) as client:
            response = client.get(f"/api/v1/recommend/outfits/{uuid.uuid4()}")
        assert response.status_code == 401


class TestRenameOutfit:
    def test_happy_path_renames(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            outfit_id = _generate_outfit(client, [ready_closet["top"]])["id"]

            response = client.patch(
                f"/api/v1/recommend/outfits/{outfit_id}/title", json={"title": "Friday client dinner"}
            )

        assert response.status_code == 200
        assert response.json() == {"id": outfit_id, "title": "Friday client dinner"}
        with get_engine().begin() as conn:
            result = conn.execute(text("SELECT title FROM outfits WHERE id = :id"), {"id": outfit_id})
            row = result.mappings().fetchone()
        assert row is not None
        assert row["title"] == "Friday client dinner"

    def test_rejects_blank_title(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            outfit_id = _generate_outfit(client, [ready_closet["top"]])["id"]

            response = client.patch(f"/api/v1/recommend/outfits/{outfit_id}/title", json={"title": "   "})

        assert response.status_code == 422

    def test_404_for_nonexistent_or_foreign_outfit(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            response = client.patch(f"/api/v1/recommend/outfits/{uuid.uuid4()}/title", json={"title": "New title"})
        assert response.status_code == 404


class TestLogOutfitWorn:
    def test_writes_outfit_and_item_wears_once_per_day(self, ready_closet: dict[str, str]) -> None:
        item_ids = [ready_closet["top"], ready_closet["bottom"]]
        with _client_as(USER_READY) as client:
            outfit_id = _generate_outfit(client, item_ids)["id"]

            first = client.post(f"/api/v1/recommend/outfits/{outfit_id}/wear")
            second = client.post(f"/api/v1/recommend/outfits/{outfit_id}/wear")

        assert first.status_code == 204
        assert second.status_code == 204

        with get_engine().begin() as conn:
            outfit_wear_count = conn.execute(
                text("SELECT count(*) FROM outfit_wears WHERE outfit_id = :id"), {"id": outfit_id}
            ).scalar_one()
            item_wear_count = conn.execute(
                text("SELECT count(*) FROM item_wears WHERE item_id = ANY(:ids)"), {"ids": item_ids}
            ).scalar_one()
        assert outfit_wear_count == 1
        assert item_wear_count == 2

        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM outfit_wears WHERE outfit_id = :id"), {"id": outfit_id})
            conn.execute(text("DELETE FROM item_wears WHERE item_id = ANY(:ids)"), {"ids": item_ids})

    def test_skips_an_item_no_longer_owned(self, ready_closet: dict[str, str]) -> None:
        removable = _insert_item(USER_READY, "belt", name="Removable belt")
        with _client_as(USER_READY) as client:
            outfit_id = _generate_outfit(client, [ready_closet["top"], removable])["id"]

            with get_engine().begin() as conn:
                conn.execute(text("DELETE FROM wardrobe_items WHERE id = :id"), {"id": removable})

            response = client.post(f"/api/v1/recommend/outfits/{outfit_id}/wear")

        assert response.status_code == 204
        with get_engine().begin() as conn:
            outfit_wear_count = conn.execute(
                text("SELECT count(*) FROM outfit_wears WHERE outfit_id = :id"), {"id": outfit_id}
            ).scalar_one()
            conn.execute(text("DELETE FROM outfit_wears WHERE outfit_id = :id"), {"id": outfit_id})
        assert outfit_wear_count == 1

    def test_404_for_nonexistent_or_foreign_outfit(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            response = client.post(f"/api/v1/recommend/outfits/{uuid.uuid4()}/wear")
        assert response.status_code == 404


class TestDeleteOutfit:
    def test_happy_path_deletes_and_cascades_wears(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            outfit_id = _generate_outfit(client, [ready_closet["top"]])["id"]
            client.post(f"/api/v1/recommend/outfits/{outfit_id}/wear")

            response = client.delete(f"/api/v1/recommend/outfits/{outfit_id}")

        assert response.status_code == 204
        with get_engine().begin() as conn:
            outfit_row = conn.execute(text("SELECT id FROM outfits WHERE id = :id"), {"id": outfit_id}).fetchone()
            wear_row = conn.execute(
                text("SELECT id FROM outfit_wears WHERE outfit_id = :id"), {"id": outfit_id}
            ).fetchone()
        assert outfit_row is None
        assert wear_row is None  # cascaded

    def test_404_for_nonexistent_or_foreign_outfit(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            response = client.delete(f"/api/v1/recommend/outfits/{uuid.uuid4()}")
        assert response.status_code == 404


class TestToggleOutfitFavorite:
    def test_flips_favorite_and_does_not_delete(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            outfit_id = _generate_outfit(client, [ready_closet["top"]])["id"]

            # Already favorite=true from generation (design-decisions.md
            # §42) — the first toggle here flips it off, not on.
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
        assert row is not None  # still exists — unfavoriting toggles, never deletes
        assert row["favorite"] is True

    def test_404_for_nonexistent_or_foreign_outfit(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            response = client.post(f"/api/v1/recommend/outfits/{uuid.uuid4()}/favorite")
        assert response.status_code == 404
