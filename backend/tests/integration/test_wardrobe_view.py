"""Integration test for GET /wardrobe/items (T016).

Uses the db_session fixture (rolled back on teardown) so these hit the real
Postgres/JSONB schema without touching production data, and dependency
overrides so auth/session don't require a live JWT or a second connection.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from whattowear.api import app
from whattowear.auth import get_current_user_id
from whattowear.db import get_session
from whattowear.models import WardrobeItemRow


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    yield TestClient(app), db_session
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user_id, None)


def _as_user(user_id) -> None:
    app.dependency_overrides[get_current_user_id] = lambda: str(user_id)


def _item(user_id, **overrides) -> WardrobeItemRow:
    defaults = dict(
        user_id=user_id,
        category="top",
        colors=["#ffffff"],
        formality="casual",
        warmth=1,
        season=["summer"],
        source="catalog",
    )
    defaults.update(overrides)
    return WardrobeItemRow(**defaults)


def test_empty_closet_returns_empty_list_not_error(client):
    c, _ = client
    _as_user(uuid.uuid4())

    r = c.get("/wardrobe/items")

    assert r.status_code == 200
    assert r.json() == []


def test_two_user_isolation(client):
    c, session = client
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    session.add(_item(user_a, category="top"))
    session.add(_item(user_b, category="bottom"))
    session.commit()

    _as_user(user_a)
    resp_a = c.get("/wardrobe/items")
    _as_user(user_b)
    resp_b = c.get("/wardrobe/items")

    assert [i["category"] for i in resp_a.json()] == ["top"]
    assert [i["category"] for i in resp_b.json()] == ["bottom"]


def test_200_item_closet_returns_fully_in_one_call(client):
    """SC-001: closet view returns in a single request up to 200 items."""
    c, session = client
    user_id = uuid.uuid4()
    session.add_all(_item(user_id) for _ in range(200))
    session.commit()

    _as_user(user_id)
    r = c.get("/wardrobe/items")

    assert r.status_code == 200
    assert len(r.json()) == 200


def test_missing_bearer_token_rejected(client):
    c, _ = client
    app.dependency_overrides.pop(get_current_user_id, None)

    r = c.get("/wardrobe/items")

    assert r.status_code == 401
