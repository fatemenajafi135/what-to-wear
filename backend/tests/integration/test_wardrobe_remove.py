"""Integration test for DELETE /wardrobe/items/{id} (T031).

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


def _item(session, user_id, **overrides) -> WardrobeItemRow:
    defaults = dict(
        user_id=user_id, category="top", colors=["#ffffff"],
        formality="casual", warmth=1, season=["summer"], source="catalog",
    )
    defaults.update(overrides)
    row = WardrobeItemRow(**defaults)
    session.add(row)
    session.commit()
    return row


def test_delete_removes_only_the_target_item(client):
    c, session = client
    user_id = uuid.uuid4()
    target = _item(session, user_id, category="jeans")
    keep = _item(session, user_id, category="sweater")
    _as_user(user_id)

    r = c.delete(f"/wardrobe/items/{target.id}")

    assert r.status_code == 204
    assert r.content == b""
    closet = c.get("/wardrobe/items").json()
    assert [i["category"] for i in closet] == ["sweater"]


def test_repeated_delete_returns_404_not_a_crash(client):
    c, session = client
    user_id = uuid.uuid4()
    row = _item(session, user_id)
    _as_user(user_id)

    first = c.delete(f"/wardrobe/items/{row.id}")
    second = c.delete(f"/wardrobe/items/{row.id}")

    assert first.status_code == 204
    assert second.status_code == 404


def test_cross_user_delete_returns_404(client):
    c, session = client
    owner, other = uuid.uuid4(), uuid.uuid4()
    row = _item(session, owner)

    _as_user(other)
    r = c.delete(f"/wardrobe/items/{row.id}")

    assert r.status_code == 404
    _as_user(owner)
    assert len(c.get("/wardrobe/items").json()) == 1


def test_unknown_item_returns_404(client):
    c, _ = client
    _as_user(uuid.uuid4())

    r = c.delete(f"/wardrobe/items/{uuid.uuid4()}")

    assert r.status_code == 404
