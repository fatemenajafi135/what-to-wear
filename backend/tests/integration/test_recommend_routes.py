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
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from whattowear import copy as turn_copy
from whattowear.auth import get_current_access_token, get_current_user_id
from whattowear.core.config import get_settings
from whattowear.core.db import get_engine
from whattowear.main import app
from whattowear.schema import (
    CitedSource,
    Context,
    ConversationalTurnResult,
    DimensionScore,
    Rationale,
    ScoredOutfit,
    SuggestResult,
)

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
        "photo_path": overrides.pop("photo_path", None),
        **overrides,
    }
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO wardrobe_items (id, user_id, category, colors, formality, warmth, season, source, "
                "name, photo_path)"
                " VALUES (:id, :user_id, :category, :colors, :formality, :warmth, :season, :source, :name,"
                " :photo_path)"
            ),
            row,
        )
    return item_id


def _insert_outfit(
    user_id: str,
    item_ids: list[str],
    *,
    title: str = "Outfit",
    match_label: str = "great",
    created_at: datetime | None = None,
) -> str:
    """Direct-SQL outfit insert for pagination tests (gh-28) — bypasses
    `SupabaseOutfitRepository.create` (which always defaults `created_at` to
    `now()`) so tests can seed many rows with distinct, controllable
    timestamps to prove `sort=date` stays stable across pages, without
    going through the full mocked-pipeline `_generate_outfit` HTTP round
    trip for every row."""
    outfit_id = str(uuid.uuid4())
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO outfits (id, user_id, occasion, meta_line, rationale_text, match_label,"
                " item_ids, title, favorite, created_at)"
                " VALUES (:id, :user_id, :occasion, :meta_line, :rationale_text, :match_label,"
                " :item_ids, :title, false, :created_at)"
            ),
            {
                "id": outfit_id,
                "user_id": user_id,
                "occasion": title,
                "meta_line": "",
                "rationale_text": "",
                "match_label": match_label,
                "item_ids": item_ids,
                "title": title,
                "created_at": created_at or datetime.now(UTC),
            },
        )
    return outfit_id


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
        conn.execute(text("DELETE FROM messages WHERE user_id = :u"), {"u": USER_READY})
        conn.execute(text("DELETE FROM sessions WHERE user_id = :u"), {"u": USER_READY})


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


def _scored_outfit(items: list[str], quality: float, cites: list[str]) -> ScoredOutfit:
    """`quality` drives every dimension score equally, so
    `equal_weighted_average(outfit.scores)` — what `match_label` actually
    reads — comes out to exactly `quality`. `rank_score` below is a fixed,
    deliberately unrelated placeholder shaped like a real
    `combine.fit_first_lexicographic` value (an internal ordering key, not
    a 0-1 quality score) precisely so these tests would fail if match
    labeling ever again read `outfit.rank_score` instead of the
    dimension-score average."""
    return ScoredOutfit(
        items=items,
        rationale=[Rationale(text="A clean, casual pairing.", cites=cites)],
        scores=[
            DimensionScore(dimension="color_harmony", value=quality, reason="ok"),
            DimensionScore(dimension="formality_coherence", value=quality, reason="ok"),
            DimensionScore(dimension="weather_fitness", value=quality, reason="ok"),
            DimensionScore(dimension="silhouette_balance", value=quality, reason="ok"),
        ],
        rank_score=900.7,
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
    outfit = _scored_outfit(item_ids, quality=0.85, cites=cites or [])
    result = SuggestResult(outfits=[outfit], sources=sources or [])
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {"result": result, "note": None}
    with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
        response = client.post("/api/v1/recommend/messages", json={"message": occasion})
    assert response.status_code == 200
    outfits = response.json()["outfits"]
    assert len(outfits) == 1
    return outfits[0]


def _send_turn(
    client: TestClient,
    message: str,
    thread_id: str | None = None,
    reply_text: str = "Got it.",
    **slots: object,
) -> dict:
    """feature 016 — posts to the new conversational endpoint with the LLM call itself mocked,
    patched at the route module's own import site (same "patch where it's imported" pattern
    `_generate_outfit` already established for `get_compiled_graph`). `slots` become the mocked
    extraction's own fields (e.g. `occasion="wedding"`, `formality="formal"`)."""
    fake_result = ConversationalTurnResult(reply_text=reply_text, **slots)  # type: ignore[arg-type]
    with patch("whattowear.api.v1.routes.recommend.conversation.reply", return_value=fake_result):
        response = client.post(
            "/api/v1/recommend/turns",
            json={"message": message, "thread_id": thread_id},
        )
    assert response.status_code == 200
    return response.json()


def _real_graph_with_mocked_invoke(result: SuggestResult, note: str | None) -> MagicMock:
    """Compiles the REAL pipeline graph against a fixture (no-DB) repository, so
    `get_state`/`update_state` exercise the real checkpointer (design-decisions.md §47) — the
    thing feature 016's slot accumulation/composition actually depends on. Only `.invoke` itself
    is replaced (via the caller's own `patch.object`, so it's restored afterward), which is what
    keeps this from ever calling the real pipeline/LLM."""
    from whattowear.adapters.closet_fixture import FixtureClosetRepository
    from whattowear.pipeline.graph import get_compiled_graph as real_get_compiled_graph

    return real_get_compiled_graph(FixtureClosetRepository())


def _outfit_row(outfit_id: str) -> dict:
    with get_engine().begin() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT user_id, occasion, meta_line, rationale_text, match_label, item_ids, favorite, "
                    "title, rationale_with_citations, citations, dimension_scores, thread_id "
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


class TestSendTurn:
    """feature 016, contracts/recommend-turns.md — the new conversational endpoint."""

    def test_first_call_mints_a_thread_id_and_returns_a_reply(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            turn = _send_turn(
                client, "something for a wedding", reply_text="Got it — what's the occasion?", occasion="wedding"
            )

        assert turn["thread_id"]
        assert turn["reply_text"] == "Got it — what's the occasion?"
        assert turn["occasion"] == "wedding"
        assert turn["formality"] is None

    def test_second_call_on_same_thread_is_told_the_already_known_slots(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            first = _send_turn(client, "something for a wedding", occasion="wedding")
            thread_id = first["thread_id"]

            fake_result = ConversationalTurnResult(reply_text="Got it.", formality="formal")
            with patch("whattowear.api.v1.routes.recommend.conversation.reply", return_value=fake_result) as mock_reply:
                response = client.post(
                    "/api/v1/recommend/turns",
                    json={"message": "pretty formal", "thread_id": thread_id},
                )

        assert response.status_code == 200
        known_slots_arg = mock_reply.call_args.args[1]
        assert known_slots_arg.get("occasion") == "wedding"

    def test_empty_message_is_rejected(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            response = client.post("/api/v1/recommend/turns", json={"message": "   "})
        assert response.status_code == 422

    def test_turn_cap_is_enforced_without_an_llm_call(self, ready_closet: dict[str, str]) -> None:
        """design-decisions.md §48 — once the cap is exceeded, no further LLM call happens at
        all, not just a differently-worded one."""
        cap = get_settings().wtw_conversation_turn_cap

        with _client_as(USER_READY) as client:
            thread_id = None
            for i in range(cap):
                turn = _send_turn(client, f"message {i}", thread_id=thread_id, reply_text=f"reply {i}")
                thread_id = turn["thread_id"]

            with patch("whattowear.api.v1.routes.recommend.conversation.reply") as mock_reply:
                response = client.post(
                    "/api/v1/recommend/turns",
                    json={"message": "one more", "thread_id": thread_id},
                )

        assert response.status_code == 200
        assert response.json()["reply_text"] == turn_copy.TURN_CAP_REACHED
        mock_reply.assert_not_called()

    def test_llm_call_failure_returns_fixed_copy_not_a_5xx(self, ready_closet: dict[str, str]) -> None:
        """FR-010 — a genuine call failure degrades to the fixed CALL_FAILED reply, never a
        5xx (mirrors vision.py's own call-failure philosophy)."""
        with patch("whattowear.api.v1.routes.recommend.conversation.reply", side_effect=RuntimeError("gateway down")):
            with _client_as(USER_READY) as client:
                response = client.post("/api/v1/recommend/turns", json={"message": "hello"})

        assert response.status_code == 200
        assert response.json()["reply_text"] == turn_copy.CALL_FAILED

    def test_a_failed_turn_does_not_block_start_styling(self, ready_closet: dict[str, str]) -> None:
        """SC-005 — whatever slots were accumulated before the failure are still used."""
        result = SuggestResult(outfits=[], sources=[])
        mock_graph = _real_graph_with_mocked_invoke(result, "Nothing to show.")

        with _client_as(USER_READY) as client:
            first = _send_turn(client, "something for a wedding", occasion="wedding")
            thread_id = first["thread_id"]

            with patch(
                "whattowear.api.v1.routes.recommend.conversation.reply", side_effect=RuntimeError("gateway down")
            ):
                failed = client.post(
                    "/api/v1/recommend/turns",
                    json={"message": "keep going", "thread_id": thread_id},
                )
            assert failed.status_code == 200
            assert failed.json()["reply_text"] == turn_copy.CALL_FAILED

            with (
                patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph),
                patch.object(
                    mock_graph, "invoke", return_value={"result": result, "note": "Nothing to show."}
                ) as mock_invoke,
            ):
                styling = client.post(
                    "/api/v1/recommend/messages",
                    json={"message": "keep going", "thread_id": thread_id},
                )

        assert styling.status_code == 200
        invoke_input = mock_invoke.call_args.args[0]
        assert invoke_input["occasion"] == "wedding"


class TestSendMessage:
    """specs/009-suggestion-pager/contracts/recommend.md, extended by
    design-decisions.md §42: every outfit this route returns is already
    persisted by the time the response is sent, regardless of favorite
    state (§43: "saved" and "favorite" are independent — a fresh row is
    saved unconditionally but starts unfavorited, since favorite is the
    user's own, not-yet-expressed preference) — verified below by reading
    the row back, not just checking the 2xx."""

    def test_blocked_closet_is_rejected_and_pipeline_never_invoked(self, blocked_closet: None) -> None:
        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph") as mock_get_graph:
            with _client_as(USER_BLOCKED) as client:
                response = client.post("/api/v1/recommend/messages", json={"message": "business casual"})
            mock_get_graph.assert_not_called()
        assert response.status_code == 403

    def test_happy_path_returns_only_owned_items_and_no_numbers(self, ready_closet: dict[str, str]) -> None:
        outfit = _scored_outfit(
            [ready_closet["top"], ready_closet["bottom"], ready_closet["shoes"]],
            quality=0.85,
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
        assert outfit_body["favorite"] is False  # saved, but not favorited yet (§43)
        assert "[1]" not in outfit_body["rationale_text"]  # no citation markers on the card (§33/§35)
        assert outfit_body["meta_line"] == "business casual for a rainy commute · rain"
        assert "rank_score" not in outfit_body
        assert "citations" not in outfit_body  # not on the card shape — only on the stored row (§38/§42)
        assert body["thread_id"]

        # Read the row back directly — a 2xx proves nothing about what was
        # actually stored (handoff §10).
        row = _outfit_row(outfit_body["id"])
        assert str(row["user_id"]) == USER_READY
        assert row["favorite"] is False
        assert row["title"] == "business casual for a rainy commute"  # seeded from occasion (§36)
        assert row["rationale_with_citations"] == "A clean, casual pairing. [1]"
        assert row["citations"] == [{"number": 1, "text": "Pair casual denim with a relaxed top."}]
        assert row["dimension_scores"] == [
            {"dimension": "color_harmony", "value": 0.85},
            {"dimension": "formality_coherence", "value": 0.85},
            {"dimension": "weather_fitness", "value": 0.85},
            {"dimension": "silhouette_balance", "value": 0.85},
        ]

    def test_multiple_outfits_returned_in_rank_order_below_floor_dropped_and_all_saved(
        self, ready_closet: dict[str, str]
    ) -> None:
        great = _scored_outfit([ready_closet["top"]], quality=0.85, cites=[])
        good = _scored_outfit([ready_closet["bottom"]], quality=0.65, cites=[])
        below_floor = _scored_outfit([ready_closet["shoes"]], quality=0.2, cites=[])
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
        below_floor = _scored_outfit([ready_closet["top"]], quality=0.1, cites=[])
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
        outfit = _scored_outfit([ready_closet["top"]], quality=0.85, cites=[])
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
        outfit = _scored_outfit([ready_closet["top"], catalog_item_id], quality=0.85, cites=[])
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

    def test_first_message_creates_a_session_and_a_user_message_row(self, ready_closet: dict[str, str]) -> None:
        """design-decisions.md §44: a session is written on the thread's
        first message — no separate archive step. Session id IS the
        thread_id, not a second generated one. design-decisions.md §50:
        `POST /recommend/turns` is the sole writer of `user_message` rows
        from feature 016 on, since every composer send reaches it first."""
        with _client_as(USER_READY) as client:
            turn = _send_turn(client, "Rainy commute", reply_text="Got it — what's the occasion?")

        thread_id = turn["thread_id"]
        with get_engine().begin() as conn:
            session_row = conn.execute(text("SELECT id, user_id FROM sessions WHERE id = :id"), {"id": thread_id}).one()
            message_rows = conn.execute(
                text("SELECT kind, text FROM messages WHERE session_id = :id ORDER BY created_at"),
                {"id": thread_id},
            ).all()

        assert str(session_row.user_id) == USER_READY
        assert [(row.kind, row.text) for row in message_rows] == [
            ("user_message", "Rainy commute"),
            ("conversational_turn", "Got it — what's the occasion?"),
        ]

    def test_start_styling_no_longer_writes_its_own_user_message_row(self, ready_closet: dict[str, str]) -> None:
        """design-decisions.md §50: with every composer send already reaching
        `POST /recommend/turns` first, `POST /recommend/messages` writing a second
        `user_message` row for the same text would duplicate the transcript — it stops
        writing one entirely. Two new rows appear instead: `conversational_turn` (from
        the turns call) and `wrap_up` (feature 016's Start-styling summary, §49)."""
        result = SuggestResult(outfits=[], sources=[])
        mock_graph = _real_graph_with_mocked_invoke(result, "Nothing to show.")

        with _client_as(USER_READY) as client:
            turn = _send_turn(client, "Rainy commute")
            thread_id = turn["thread_id"]
            with (
                patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph),
                patch.object(mock_graph, "invoke", return_value={"result": result, "note": "Nothing to show."}),
            ):
                client.post(
                    "/api/v1/recommend/messages",
                    json={"message": "Rainy commute", "thread_id": thread_id},
                )

        with get_engine().begin() as conn:
            kinds = [
                row.kind
                for row in conn.execute(
                    text("SELECT kind FROM messages WHERE session_id = :id ORDER BY created_at"),
                    {"id": thread_id},
                ).all()
            ]
        assert kinds == ["user_message", "conversational_turn", "styling_reply", "wrap_up"]
        assert kinds.count("user_message") == 1

    def test_second_message_reuses_the_same_session_and_appends_messages(self, ready_closet: dict[str, str]) -> None:
        """No second session row is created on a follow-up — the same
        thread_id upserts (design-decisions.md §44)."""
        result = SuggestResult(outfits=[], sources=[])
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"result": result, "note": "Nothing to show."}

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                first = client.post("/api/v1/recommend/messages", json={"message": "Rainy commute"})
                thread_id = first.json()["thread_id"]
                client.post(
                    "/api/v1/recommend/messages",
                    json={"message": "something warmer", "thread_id": thread_id},
                )

        with get_engine().begin() as conn:
            session_count = conn.execute(
                text("SELECT count(*) FROM sessions WHERE id = :id"), {"id": thread_id}
            ).scalar_one()
            message_count = conn.execute(
                text("SELECT count(*) FROM messages WHERE session_id = :id"), {"id": thread_id}
            ).scalar_one()

        assert session_count == 1
        # 2 styling_reply + 2 wrap_up — no user_message here since feature 016 (§50):
        # `POST /recommend/messages` alone never wrote one for either call.
        assert message_count == 4

    def test_persisted_outfits_link_back_to_the_producing_thread(self, ready_closet: dict[str, str]) -> None:
        """design-decisions.md §45: outfits.thread_id is set from the
        request's own thread_id, and the styling_reply message's
        outfit_ids matches what was actually persisted."""
        outfit = _scored_outfit([ready_closet["top"]], quality=0.85, cites=[])
        result = SuggestResult(outfits=[outfit], sources=[])
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"result": result, "note": None}

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                response = client.post("/api/v1/recommend/messages", json={"message": "smart casual"})

        body = response.json()
        thread_id = body["thread_id"]
        outfit_id = body["outfits"][0]["id"]

        row = _outfit_row(outfit_id)
        assert str(row["thread_id"]) == thread_id

        with get_engine().begin() as conn:
            styling_reply = conn.execute(
                text("SELECT outfit_ids FROM messages WHERE session_id = :id AND kind = 'styling_reply'"),
                {"id": thread_id},
            ).one()
        assert [str(oid) for oid in styling_reply.outfit_ids] == [outfit_id]

    def test_wrap_up_text_is_returned_and_persisted(self, ready_closet: dict[str, str]) -> None:
        """design-decisions.md §49 — a Python-templated summary, not a second LLM call, shown
        as its own assistant message before the outfits."""
        result = SuggestResult(outfits=[], sources=[])
        mock_graph = MagicMock()
        mock_graph.get_state.return_value.values = {}
        mock_graph.invoke.return_value = {"result": result, "note": "Nothing to show."}

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                response = client.post("/api/v1/recommend/messages", json={"message": "smart casual"})

        body = response.json()
        assert body["wrap_up_text"] == "Styling for smart casual."
        thread_id = body["thread_id"]
        with get_engine().begin() as conn:
            wrap_up = conn.execute(
                text("SELECT text FROM messages WHERE session_id = :id AND kind = 'wrap_up'"),
                {"id": thread_id},
            ).one()
        assert wrap_up.text == "Styling for smart casual."

    def test_first_invoke_composes_from_accumulated_slots_across_turns(self, ready_closet: dict[str, str]) -> None:
        """design-decisions.md §47/§49 — the load-bearing check: a formality mentioned in a
        LATER conversational turn than the occasion must both be present in what's actually
        passed to graph.invoke, verified by inspecting the invoke call's own arguments — not
        by looking at the outfits (handoff §8)."""
        result = SuggestResult(outfits=[], sources=[])
        mock_graph = _real_graph_with_mocked_invoke(result, "Nothing to show.")

        with _client_as(USER_READY) as client:
            first = _send_turn(client, "something for a wedding", occasion="wedding")
            thread_id = first["thread_id"]
            _send_turn(client, "keep it black tie", thread_id=thread_id, formality="black_tie")

            with (
                patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph),
                patch.object(
                    mock_graph, "invoke", return_value={"result": result, "note": "Nothing to show."}
                ) as mock_invoke,
            ):
                client.post(
                    "/api/v1/recommend/messages",
                    json={"message": "keep it black tie", "thread_id": thread_id},
                )

        invoke_input = mock_invoke.call_args.args[0]
        assert invoke_input["occasion"] == "wedding"
        assert invoke_input["formality"] == "black_tie"

    def test_same_slot_overwritten_by_a_later_turn_wins(self, ready_closet: dict[str, str]) -> None:
        """FR-004 — distinct from the test above, which proves two DIFFERENT slots both
        arrive: this exercises the checkpointer's per-key overwrite semantics §47 relies on
        for the SAME slot stated twice, differently."""
        result = SuggestResult(outfits=[], sources=[])
        mock_graph = _real_graph_with_mocked_invoke(result, "Nothing to show.")

        with _client_as(USER_READY) as client:
            first = _send_turn(client, "office wear please", occasion="office", formality="business_casual")
            thread_id = first["thread_id"]
            _send_turn(client, "actually more relaxed", thread_id=thread_id, formality="casual")

            with (
                patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph),
                patch.object(
                    mock_graph, "invoke", return_value={"result": result, "note": "Nothing to show."}
                ) as mock_invoke,
            ):
                client.post(
                    "/api/v1/recommend/messages",
                    json={"message": "actually more relaxed", "thread_id": thread_id},
                )

        invoke_input = mock_invoke.call_args.args[0]
        assert invoke_input["formality"] == "casual"

    def test_no_slots_extracted_falls_back_to_the_raw_message_text(self, ready_closet: dict[str, str]) -> None:
        """The handoff's own fallback rule: when nothing was ever extracted, the accumulated
        raw user text is what `occasion` becomes — exactly 008's original behaviour."""
        result = SuggestResult(outfits=[], sources=[])
        mock_graph = _real_graph_with_mocked_invoke(result, "Nothing to show.")

        with _client_as(USER_READY) as client:
            first = _send_turn(client, "hi there")  # extracts nothing
            thread_id = first["thread_id"]

            with (
                patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph),
                patch.object(
                    mock_graph, "invoke", return_value={"result": result, "note": "Nothing to show."}
                ) as mock_invoke,
            ):
                client.post(
                    "/api/v1/recommend/messages",
                    json={"message": "hi there", "thread_id": thread_id},
                )

        invoke_input = mock_invoke.call_args.args[0]
        assert invoke_input["occasion"] == "hi there"
        assert "formality" not in invoke_input

    def test_refinement_tap_uses_unmodified_raw_text_not_slots(self, ready_closet: dict[str, str]) -> None:
        """design-decisions.md §49: once a thread has had one real invoke (original_context is
        set), a later tap must use 008's unmodified raw-text refinement behaviour — never
        recompose from slots, which would starve `_parse_refinement_intent` of the keyword
        signal it needs."""
        result = SuggestResult(outfits=[], sources=[])
        mock_graph = _real_graph_with_mocked_invoke(result, "Nothing to show.")

        with _client_as(USER_READY) as client:
            first = _send_turn(client, "something for a wedding", occasion="wedding", formality="black_tie")
            thread_id = first["thread_id"]

            config = {"configurable": {"thread_id": thread_id}}
            # Simulate a completed first invoke — gather_context is the only place
            # original_context is normally set, so it's seeded directly here.
            mock_graph.update_state(config, {"original_context": Context(occasion="wedding", formality="black_tie")})

            with (
                patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph),
                patch.object(
                    mock_graph, "invoke", return_value={"result": result, "note": "Nothing to show."}
                ) as mock_invoke,
            ):
                client.post(
                    "/api/v1/recommend/messages",
                    json={"message": "actually, warmer please", "thread_id": thread_id},
                )

        invoke_input = mock_invoke.call_args.args[0]
        assert invoke_input == {
            "occasion": "actually, warmer please",
            "thread_id": thread_id,
            "user_id": USER_READY,
            "approach": "grounded",
        }


class TestListSessions:
    """specs/011-chat-history/contracts/recommend.md — Chat history's list."""

    def test_returns_only_the_callers_sessions_most_recently_active_first(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            older = _send_turn(client, "Older conversation")
            _send_turn(client, "Newer conversation")

        older_thread_id = older["thread_id"]

        with _client_as(USER_READY) as client:
            response = client.get("/api/v1/recommend/sessions")

        assert response.status_code == 200
        sessions = response.json()["sessions"]
        assert len(sessions) == 2
        assert sessions[0]["preview"] == "Newer conversation"  # most recently active first
        assert sessions[1]["id"] == older_thread_id
        assert sessions[0]["message_count"] == 2  # one user_message + one conversational_turn
        assert sessions[0]["outfit_count"] == 0

    def test_outfit_count_reflects_only_outfits_linked_to_that_thread(self, ready_closet: dict[str, str]) -> None:
        outfit = _scored_outfit([ready_closet["top"]], quality=0.85, cites=[])
        result = SuggestResult(outfits=[outfit], sources=[])
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"result": result, "note": None}

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                response = client.post("/api/v1/recommend/messages", json={"message": "smart casual"})

        with _client_as(USER_READY) as client:
            sessions = client.get("/api/v1/recommend/sessions").json()["sessions"]

        assert sessions[0]["id"] == response.json()["thread_id"]
        assert sessions[0]["outfit_count"] == 1

    def test_a_pre_existing_outfit_with_no_thread_link_counts_toward_no_session(
        self, ready_closet: dict[str, str]
    ) -> None:
        """FR-009/SC-004: an outfit that predates this feature's linking
        column (thread_id IS NULL) must never be attributed to any
        session, even one that happens to share the same user/occasion."""
        result = SuggestResult(outfits=[], sources=[])
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"result": result, "note": "Nothing to show."}

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                response = client.post("/api/v1/recommend/messages", json={"message": "Rainy commute"})

        # Simulate an old-style, pre-011 outfit row: same user/occasion,
        # no thread_id — inserted directly, bypassing the route.
        with get_engine().begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO outfits (user_id, occasion, meta_line, rationale_text, match_label, item_ids, "
                    "title) VALUES (:user_id, 'Rainy commute', 'meta', 'rationale', 'great', '{}', 'Rainy commute')"
                ),
                {"user_id": USER_READY},
            )

        with _client_as(USER_READY) as client:
            sessions = client.get("/api/v1/recommend/sessions").json()["sessions"]

        assert sessions[0]["id"] == response.json()["thread_id"]
        assert sessions[0]["outfit_count"] == 0

    def test_empty_list_for_a_user_with_no_sessions(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            response = client.get("/api/v1/recommend/sessions")
        assert response.status_code == 200
        assert response.json()["sessions"] == []

    def test_does_not_return_another_users_sessions(self, ready_closet: dict[str, str], blocked_closet: None) -> None:
        result = SuggestResult(outfits=[], sources=[])
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"result": result, "note": "Nothing to show."}

        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                client.post("/api/v1/recommend/messages", json={"message": "Rainy commute"})

        with _client_as(USER_BLOCKED) as client:
            response = client.get("/api/v1/recommend/sessions")

        assert response.status_code == 200
        assert response.json()["sessions"] == []


class TestGetSession:
    """specs/011-chat-history/contracts/recommend.md — Session detail, the
    full read-only transcript."""

    def test_happy_path_returns_ordered_messages_with_roles(self, ready_closet: dict[str, str]) -> None:
        result = SuggestResult(outfits=[], sources=[])
        mock_graph = _real_graph_with_mocked_invoke(result, "Nothing to show.")

        with _client_as(USER_READY) as client:
            turn = _send_turn(client, "Rainy commute", reply_text="Got it.")
            thread_id = turn["thread_id"]
            with (
                patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph),
                patch.object(mock_graph, "invoke", return_value={"result": result, "note": "Nothing to show."}),
            ):
                client.post(
                    "/api/v1/recommend/messages",
                    json={"message": "Rainy commute", "thread_id": thread_id},
                )

        with _client_as(USER_READY) as client:
            response = client.get(f"/api/v1/recommend/sessions/{thread_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == thread_id
        assert body["outfit_count"] == 0
        assert [(m["kind"], m["role"], m["text"]) for m in body["messages"]] == [
            ("user_message", "user", "Rainy commute"),
            ("conversational_turn", "assistant", "Got it."),
            ("styling_reply", "assistant", "Nothing to show."),
            ("wrap_up", "assistant", "Styling for Rainy commute."),
        ]
        assert body["messages"][2]["outfits"] == []

    def test_styling_reply_resolves_its_outfits_with_citations_no_thumbnails(
        self, ready_closet: dict[str, str]
    ) -> None:
        """design-decisions.md §46: the archived bubble's citation badges
        come from the outfit's own rationale_with_citations/citations —
        never an items/thumbnail field."""
        with _client_as(USER_READY) as client:
            outfit_body = _generate_outfit(
                client,
                [ready_closet["top"]],
                occasion="Client dinner",
                cites=["rule-1"],
                sources=[
                    CitedSource(rule_id="rule-1", source="Pair casual denim with a relaxed top.", url="", layer="L3")
                ],
            )
            thread_id = client.get("/api/v1/recommend/sessions").json()["sessions"][0]["id"]
            response = client.get(f"/api/v1/recommend/sessions/{thread_id}")

        assert response.status_code == 200
        # feature 016 appends a `wrap_up` message after `styling_reply` (design-decisions.md
        # §49) — looked up by kind rather than assumed to be the transcript's last entry.
        messages_by_kind = {m["kind"]: m for m in response.json()["messages"]}
        styling_reply = messages_by_kind["styling_reply"]
        assert len(styling_reply["outfits"]) == 1
        resolved_outfit = styling_reply["outfits"][0]
        assert resolved_outfit["id"] == outfit_body["id"]
        assert "[1]" in resolved_outfit["rationale_with_citations"]
        assert resolved_outfit["citations"] == [{"number": 1, "text": "Pair casual denim with a relaxed top."}]
        assert "items" not in resolved_outfit
        assert set(resolved_outfit.keys()) == {"id", "title", "rationale_with_citations", "citations"}

    def test_404_for_malformed_missing_or_foreign_session(
        self, ready_closet: dict[str, str], blocked_closet: None
    ) -> None:
        with _client_as(USER_READY) as client:
            malformed = client.get("/api/v1/recommend/sessions/not-a-uuid")
            missing = client.get(f"/api/v1/recommend/sessions/{uuid.uuid4()}")
        assert malformed.status_code == 404
        assert missing.status_code == 404

        result = SuggestResult(outfits=[], sources=[])
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"result": result, "note": "Nothing to show."}
        with patch("whattowear.api.v1.routes.recommend.get_compiled_graph", return_value=mock_graph):
            with _client_as(USER_READY) as client:
                thread_id = client.post("/api/v1/recommend/messages", json={"message": "Rainy commute"}).json()[
                    "thread_id"
                ]

        with _client_as(USER_BLOCKED) as client:
            foreign = client.get(f"/api/v1/recommend/sessions/{thread_id}")
        assert foreign.status_code == 404

    def test_requires_authentication(self, ready_closet: dict[str, str]) -> None:
        app.dependency_overrides.clear()
        with TestClient(app) as client:
            response = client.get(f"/api/v1/recommend/sessions/{uuid.uuid4()}")
        assert response.status_code == 401


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

    def test_pagination_offset_and_has_more_flag(self, ready_closet: dict[str, str]) -> None:
        """gh-28 — mirrors test_closet_routes.py's test_pagination_has_more_flag."""
        top = ready_closet["top"]
        base = datetime.now(UTC)
        for i in range(25):
            _insert_outfit(USER_READY, [top], title=f"Outfit {i}", created_at=base - timedelta(seconds=i))

        with _client_as(USER_READY) as client:
            first_page = client.get("/api/v1/recommend/outfits").json()
            second_page = client.get("/api/v1/recommend/outfits", params={"offset": 20}).json()

        assert first_page["total"] == 25
        assert len(first_page["outfits"]) == 20
        assert first_page["has_more"] is True
        assert len(second_page["outfits"]) == 5
        assert second_page["has_more"] is False

    def test_page_two_continues_page_ones_sort_order(self, ready_closet: dict[str, str]) -> None:
        """gh-28: page 2 of `?sort=date` must continue page 1's order, not
        re-sort a different slice — titles double as the expected order so
        the assertion doesn't have to re-derive it from timestamps."""
        top = ready_closet["top"]
        base = datetime.now(UTC)
        expected_order = [f"Outfit {i}" for i in range(25)]
        for i, title in enumerate(expected_order):
            _insert_outfit(USER_READY, [top], title=title, created_at=base - timedelta(seconds=i))

        with _client_as(USER_READY) as client:
            first_page = client.get("/api/v1/recommend/outfits", params={"sort": "date"}).json()
            second_page = client.get("/api/v1/recommend/outfits", params={"sort": "date", "offset": 20}).json()

        combined_titles = [o["title"] for o in first_page["outfits"]] + [o["title"] for o in second_page["outfits"]]
        assert combined_titles == expected_order

    def test_only_current_pages_thumbnails_are_signed(self, ready_closet: dict[str, str]) -> None:
        """The actual bug (gh-28): paginating the response while still
        signing every row's photos fixes nothing — 25 outfits, each with one
        photographed item; only the 20 on the first page may reach
        `storage.create_signed_urls`."""
        items_with_photos = [
            _insert_item(USER_READY, "t-shirt", photo_path=f"{USER_READY}/outfit-{i}.jpg") for i in range(25)
        ]
        base = datetime.now(UTC)
        for i, item_id in enumerate(items_with_photos):
            _insert_outfit(USER_READY, [item_id], title=f"Outfit {i}", created_at=base - timedelta(seconds=i))

        with (
            patch("whattowear.api.v1.routes.recommend.storage.create_signed_urls", return_value={}) as mock_sign,
            _client_as(USER_READY) as client,
        ):
            response = client.get("/api/v1/recommend/outfits")

        assert response.status_code == 200
        assert response.json()["total"] == 25
        mock_sign.assert_called_once()
        signed_paths = mock_sign.call_args.args[1]
        assert len(signed_paths) == 20  # page size — never the full 25


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
            {"dimension": "color_harmony", "value": 0.85},
            {"dimension": "formality_coherence", "value": 0.85},
            {"dimension": "weather_fitness", "value": 0.85},
            {"dimension": "silhouette_balance", "value": 0.85},
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

            # Starts unfavorited from generation (design-decisions.md §43:
            # saved unconditionally, favorite is a separate, not-yet-
            # expressed preference) — the first toggle here flips it on.
            first_toggle = client.post(f"/api/v1/recommend/outfits/{outfit_id}/favorite")
            assert first_toggle.status_code == 200
            assert first_toggle.json()["favorite"] is True

            second_toggle = client.post(f"/api/v1/recommend/outfits/{outfit_id}/favorite")
            assert second_toggle.json()["favorite"] is False

        with get_engine().begin() as conn:
            row = (
                conn.execute(text("SELECT favorite FROM outfits WHERE id = :id"), {"id": outfit_id})
                .mappings()
                .fetchone()
            )
        assert row is not None  # still exists — favoriting/unfavoriting toggles, never deletes
        assert row["favorite"] is False

    def test_404_for_nonexistent_or_foreign_outfit(self, ready_closet: dict[str, str]) -> None:
        with _client_as(USER_READY) as client:
            response = client.post(f"/api/v1/recommend/outfits/{uuid.uuid4()}/favorite")
        assert response.status_code == 404
