"""Integration tests for the closet read routes (specs/004-closet-read/
contracts/closet.md). Runs against a real local Supabase database — no
mocked database layer, matching test_health.py's existing precedent.
Requires `DATABASE_URL` in the environment, pointed at a running local
Supabase stack (`cd infra && npx supabase start`).

Identity is supplied via a FastAPI dependency override rather than a real
Supabase JWT — `get_current_user_id` itself is already covered end to end
by tests/integration/test_whoami.py and tests/unit/test_auth.py; this file
is about the closet routes' own behavior (ownership, filtering, pagination,
404 shape), not re-proving JWT verification. RLS's own guarantee — which
this backend's connection doesn't benefit from directly (BYPASSRLS) — is
proven independently by test_wardrobe_rls.py.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from whattowear.auth import get_current_user_id
from whattowear.core.db import get_engine
from whattowear.main import app

USER_A = str(uuid.uuid4())
USER_B = str(uuid.uuid4())


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
        **overrides,
    }
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO wardrobe_items (id, user_id, category, colors, formality, warmth, season, source, name)"
                " VALUES (:id, :user_id, :category, :colors, :formality, :warmth, :season, :source, :name)"
            ),
            {**row, "name": row.get("name")},
        )
    return item_id


@pytest.fixture
def seeded_items() -> Iterator[dict[str, list[str]]]:
    a_top = _insert_item(USER_A, "t-shirt", name="A's tee")
    a_dress = _insert_item(USER_A, "dress")  # full_body — should filter under Bottoms
    b_top = _insert_item(USER_B, "t-shirt", name="B's tee")
    yield {"user_a": [a_top, a_dress], "user_b": [b_top]}
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM wardrobe_items WHERE user_id IN (:a, :b)"), {"a": USER_A, "b": USER_B})


def _client_as(user_id: str) -> TestClient:
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def test_missing_token_rejected() -> None:
    app.dependency_overrides.clear()
    with TestClient(app) as client:
        response = client.get("/api/v1/closet/items")
    assert response.status_code == 401


def test_lists_only_the_caller_own_items(seeded_items: dict[str, list[str]]) -> None:
    with _client_as(USER_A) as client:
        response = client.get("/api/v1/closet/items")

    assert response.status_code == 200
    body = response.json()
    returned_ids = {item["id"] for item in body["items"]}
    assert returned_ids == set(seeded_items["user_a"])
    assert seeded_items["user_b"][0] not in returned_ids
    assert body["total"] == 2


def test_category_filter_bottom_includes_full_body_dress(seeded_items: dict[str, list[str]]) -> None:
    with _client_as(USER_A) as client:
        response = client.get("/api/v1/closet/items", params={"category": "bottom"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["category"] == "dress"
    assert body["items"][0]["category_group"] == "full_body"


def test_category_filter_top_excludes_dress(seeded_items: dict[str, list[str]]) -> None:
    with _client_as(USER_A) as client:
        response = client.get("/api/v1/closet/items", params={"category": "top"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["category"] == "t-shirt"


def test_item_detail_returns_own_item_with_computed_fields(seeded_items: dict[str, list[str]]) -> None:
    item_id = seeded_items["user_a"][0]
    with _client_as(USER_A) as client:
        response = client.get(f"/api/v1/closet/items/{item_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == item_id
    assert body["name"] == "A's tee"
    assert body["category_group"] == "top"
    # colors.py's names are lowercase (its own dict is authored lowercase,
    # e.g. "navy": "#1b2a4a") — title-casing for display is a frontend
    # (CSS text-transform) concern, not something the API encodes.
    assert body["color_names"] == ["navy"]


def test_item_detail_404_for_foreign_item(seeded_items: dict[str, list[str]]) -> None:
    foreign_item_id = seeded_items["user_b"][0]
    with _client_as(USER_A) as client:
        response = client.get(f"/api/v1/closet/items/{foreign_item_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}


def test_item_detail_404_for_nonexistent_item() -> None:
    with _client_as(USER_A) as client:
        response = client.get(f"/api/v1/closet/items/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}


def test_item_detail_404_for_malformed_id() -> None:
    """Caught in review: a syntactically invalid uuid used to reach the
    database's `uuid` column comparison and crash with an unhandled 500
    instead of the same 404 every other not-found case gets."""
    with _client_as(USER_A) as client:
        response = client.get("/api/v1/closet/items/not-a-uuid")

    assert response.status_code == 404
    assert response.json() == {"detail": "Item not found"}


def test_pagination_has_more_flag() -> None:
    ids = [_insert_item(USER_A, "t-shirt") for _ in range(25)]
    try:
        with _client_as(USER_A) as client:
            first_page = client.get("/api/v1/closet/items").json()
            second_page = client.get("/api/v1/closet/items", params={"offset": 20}).json()

        assert first_page["total"] == 25
        assert len(first_page["items"]) == 20
        assert first_page["has_more"] is True
        assert len(second_page["items"]) == 5
        assert second_page["has_more"] is False
    finally:
        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM wardrobe_items WHERE id = ANY(:ids)"), {"ids": ids})
