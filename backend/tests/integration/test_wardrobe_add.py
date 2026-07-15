"""Integration tests for GET /catalog/items, POST /wardrobe/items, and
POST /wardrobe/items/bulk (T023, T023a).

Uses the db_session fixture (rolled back on teardown) so these hit the real
Postgres/JSONB schema without touching production data, and dependency
overrides so auth/session don't require a live JWT or a second connection.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, update

from whattowear.api import app
from whattowear.auth import get_current_user_id
from whattowear.db import get_session
from whattowear.models import CatalogItemRow, WardrobeItemRow


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    yield TestClient(app), db_session
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user_id, None)


def _as_user(user_id) -> None:
    app.dependency_overrides[get_current_user_id] = lambda: str(user_id)


def _catalog_item(session, **overrides) -> CatalogItemRow:
    defaults = dict(category="top", colors=["#ffffff"], formality="casual", warmth=1, season=["summer"])
    defaults.update(overrides)
    row = CatalogItemRow(**defaults)
    session.add(row)
    session.commit()
    return row


def test_empty_catalog_returns_empty_list_not_error(client):
    c, session = client
    # Null out real wardrobe_items -> catalog_items FK references first, or
    # the delete below hits ForeignKeyViolation against real committed rows
    # (created via manual testing) -- see test_seed.py::_clear_catalog.
    session.execute(update(WardrobeItemRow).where(WardrobeItemRow.catalog_item_id.isnot(None)).values(catalog_item_id=None))
    session.execute(delete(CatalogItemRow))
    session.commit()
    _as_user(uuid.uuid4())

    r = c.get("/catalog/items")

    assert r.status_code == 200
    assert r.json() == []


def test_add_flow(client):
    c, session = client
    catalog_row = _catalog_item(session, category="jeans", formality="smart_casual", warmth=2)
    _as_user(uuid.uuid4())

    r = c.post("/wardrobe/items", json={"catalog_item_id": str(catalog_row.id)})

    assert r.status_code == 201
    body = r.json()
    assert body["category"] == "jeans"
    assert body["formality"] == "smart_casual"

    closet = c.get("/wardrobe/items").json()
    assert len(closet) == 1
    assert closet[0]["category"] == "jeans"


def test_add_unknown_catalog_item_id_returns_404(client):
    c, _ = client
    _as_user(uuid.uuid4())

    r = c.post("/wardrobe/items", json={"catalog_item_id": str(uuid.uuid4())})

    assert r.status_code == 404


def test_add_cross_user_isolation(client):
    c, session = client
    catalog_row = _catalog_item(session, category="top")
    user_a, user_b = uuid.uuid4(), uuid.uuid4()

    _as_user(user_a)
    c.post("/wardrobe/items", json={"catalog_item_id": str(catalog_row.id)})

    _as_user(user_b)
    closet_b = c.get("/wardrobe/items").json()

    assert closet_b == []


def test_bulk_add_all_succeed(client):
    c, session = client
    a = _catalog_item(session, category="top")
    b = _catalog_item(session, category="bottom")
    _as_user(uuid.uuid4())

    r = c.post("/wardrobe/items/bulk", json={"catalog_item_ids": [str(a.id), str(b.id)]})

    assert r.status_code == 201
    assert [i["category"] for i in r.json()] == ["top", "bottom"]
    closet = c.get("/wardrobe/items").json()
    assert len(closet) == 2


def test_bulk_add_any_unknown_id_rejects_batch_atomically(client):
    c, session = client
    a = _catalog_item(session, category="top")
    _as_user(uuid.uuid4())

    r = c.post("/wardrobe/items/bulk", json={"catalog_item_ids": [str(a.id), str(uuid.uuid4())]})

    assert r.status_code == 404
    closet = c.get("/wardrobe/items").json()
    assert closet == []  # nothing added, not even the valid id
