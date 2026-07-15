"""Unit tests for crud.py CRUD functions (T015 covers list_wardrobe_items;
later stories append update/add/delete tests here)."""

from __future__ import annotations

import uuid

from whattowear import crud
from whattowear.models import WardrobeItemRow


def _add_item(db_session, user_id: uuid.UUID, **overrides) -> WardrobeItemRow:
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
    db_session.add(row)
    db_session.commit()
    return row


def test_list_wardrobe_items_empty_closet_returns_empty_list(db_session):
    assert crud.list_wardrobe_items(db_session, uuid.uuid4()) == []


def test_list_wardrobe_items_returns_all_items_with_full_attributes(db_session):
    user_id = uuid.uuid4()
    _add_item(db_session, user_id, category="jeans", colors=["#1b2a4a"], formality="smart_casual", warmth=2)
    _add_item(db_session, user_id, category="sweater", colors=["#808080"], formality="casual", warmth=3)

    items = crud.list_wardrobe_items(db_session, user_id)

    assert len(items) == 2
    categories = {i.category for i in items}
    assert categories == {"jeans", "sweater"}
    for item in items:
        assert item.colors and item.formality and item.season and item.warmth is not None


def test_list_wardrobe_items_cross_user_isolation(db_session):
    user_a, user_b = uuid.uuid4(), uuid.uuid4()
    _add_item(db_session, user_a, category="top")
    _add_item(db_session, user_b, category="bottom")
    _add_item(db_session, user_b, category="bottom")

    items_a = crud.list_wardrobe_items(db_session, user_a)
    items_b = crud.list_wardrobe_items(db_session, user_b)

    assert len(items_a) == 1
    assert len(items_b) == 2
    assert all(i.category == "top" for i in items_a)


def test_list_wardrobe_items_accessory_returned_identically_to_garment(db_session):
    """FR-005: accessories are first-class, not a lesser-featured category."""
    user_id = uuid.uuid4()
    _add_item(db_session, user_id, category="jewelry", colors=["#c19a6b"], formality="formal", warmth=0)

    items = crud.list_wardrobe_items(db_session, user_id)

    assert len(items) == 1
    item = items[0]
    assert item.category == "jewelry"
    assert item.colors == ["#c19a6b"]
    assert item.formality == "formal"
    assert item.warmth == 0
    assert item.source == "catalog"
