"""Integration test for PATCH /wardrobe/items/{id} (T027).

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
        user_id=user_id,
        category="top",
        colors=["#ffffff"],
        formality="casual",
        warmth=1,
        season=["summer"],
        source="catalog",
    )
    defaults.update(overrides)
    row = WardrobeItemRow(**defaults)
    session.add(row)
    session.commit()
    return row


def test_valid_correction(client):
    c, session = client
    user_id = uuid.uuid4()
    row = _item(session, user_id, formality="casual", warmth=2)
    _as_user(user_id)

    r = c.patch(f"/wardrobe/items/{row.id}", json={"formality": "formal"})

    assert r.status_code == 200
    body = r.json()
    assert body["formality"] == "formal"
    assert body["warmth"] == 2  # untouched


@pytest.mark.parametrize(
    "bad_body",
    [
        {"formality": "extremely_fancy"},
        {"season": ["rainy"]},
        {"warmth": 9},
        {"colors": ["notahex"]},
    ],
)
def test_invalid_field_classes_return_422_and_retain_prior_value(client, bad_body):
    c, session = client
    user_id = uuid.uuid4()
    row = _item(session, user_id, formality="casual", warmth=2)
    _as_user(user_id)

    r = c.patch(f"/wardrobe/items/{row.id}", json=bad_body)

    assert r.status_code == 422
    closet = c.get("/wardrobe/items").json()
    assert closet[0]["formality"] == "casual"
    assert closet[0]["warmth"] == 2


def test_unknown_item_returns_404(client):
    c, _ = client
    _as_user(uuid.uuid4())

    r = c.patch(f"/wardrobe/items/{uuid.uuid4()}", json={"formality": "formal"})

    assert r.status_code == 404


def test_cross_user_correction_returns_404(client):
    c, session = client
    owner, other = uuid.uuid4(), uuid.uuid4()
    row = _item(session, owner, formality="casual")

    _as_user(other)
    r = c.patch(f"/wardrobe/items/{row.id}", json={"formality": "formal"})

    assert r.status_code == 404
