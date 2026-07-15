"""Unit tests for crud.py CRUD functions (T015 covers list_wardrobe_items;
later stories append update/add/delete tests here)."""

from __future__ import annotations

import uuid

import pydantic
import pytest

from whattowear import crud
from whattowear.models import CatalogItemRow, WardrobeItemRow
from whattowear.schema import WardrobeItemPatch


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


def _add_catalog_item(db_session, **overrides) -> CatalogItemRow:
    defaults = dict(category="top", colors=["#ffffff"], formality="casual", warmth=1, season=["summer"])
    defaults.update(overrides)
    row = CatalogItemRow(**defaults)
    db_session.add(row)
    db_session.commit()
    return row


def test_list_wardrobe_items_empty_closet_returns_empty_list(db_session):
    assert crud.list_wardrobe_items(db_session, uuid.uuid4()) == []


def test_list_wardrobe_items_malformed_user_id_returns_empty_list_not_error(db_session):
    """A non-UUID user_id (e.g. /recommend's free-form field) can't own any
    wardrobe rows -- degrades to [] instead of raising."""
    assert crud.list_wardrobe_items(db_session, "string") == []
    assert crud.list_wardrobe_items(db_session, "") == []


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


# --- list_catalog_items (T018) -----------------------------------------------


def test_list_catalog_items_returns_seeded_rows(db_session):
    from sqlalchemy import delete, update

    # Null out real wardrobe_items -> catalog_items FK references first, or
    # the delete below hits ForeignKeyViolation against real committed rows
    # (created via manual testing) -- see test_seed.py::_clear_catalog.
    db_session.execute(
        update(WardrobeItemRow).where(WardrobeItemRow.catalog_item_id.isnot(None)).values(catalog_item_id=None)
    )
    db_session.execute(delete(CatalogItemRow))
    _add_catalog_item(db_session, category="top")
    _add_catalog_item(db_session, category="bottom")

    items = crud.list_catalog_items(db_session)

    assert {i.category for i in items} == {"top", "bottom"}
    assert all(i.id for i in items)


# --- add_wardrobe_item_from_catalog / bulk (T022, T022a) --------------------


def test_add_wardrobe_item_from_catalog_copies_attributes(db_session):
    catalog_row = _add_catalog_item(
        db_session, category="jeans", colors=["#1b2a4a"], formality="smart_casual", warmth=2
    )
    user_id = uuid.uuid4()

    item = crud.add_wardrobe_item_from_catalog(db_session, user_id, catalog_row.id)

    assert item is not None
    assert item.category == "jeans"
    assert item.colors == ["#1b2a4a"]
    assert item.formality == "smart_casual"
    assert item.warmth == 2
    assert item.source == "catalog"
    closet = crud.list_wardrobe_items(db_session, user_id)
    assert len(closet) == 1


def test_add_wardrobe_item_from_catalog_unknown_id_returns_none(db_session):
    assert crud.add_wardrobe_item_from_catalog(db_session, uuid.uuid4(), uuid.uuid4()) is None


def test_add_wardrobe_item_from_catalog_twice_creates_two_independent_rows(db_session):
    catalog_row = _add_catalog_item(db_session, category="tee")
    user_id = uuid.uuid4()

    first = crud.add_wardrobe_item_from_catalog(db_session, user_id, catalog_row.id)
    second = crud.add_wardrobe_item_from_catalog(db_session, user_id, catalog_row.id)

    assert first.id != second.id
    assert len(crud.list_wardrobe_items(db_session, user_id)) == 2


def test_add_wardrobe_item_from_catalog_accessory_works_identically(db_session):
    """FR-005: adding an accessory-category catalog item works like any other."""
    catalog_row = _add_catalog_item(db_session, category="scarf", formality="formal")
    user_id = uuid.uuid4()

    item = crud.add_wardrobe_item_from_catalog(db_session, user_id, catalog_row.id)

    assert item.category == "scarf"
    assert item.formality == "formal"


def test_add_wardrobe_items_from_catalog_bulk_inserts_all(db_session):
    a = _add_catalog_item(db_session, category="top")
    b = _add_catalog_item(db_session, category="bottom")
    user_id = uuid.uuid4()

    items = crud.add_wardrobe_items_from_catalog(db_session, user_id, [a.id, b.id])

    assert [i.category for i in items] == ["top", "bottom"]
    assert len(crud.list_wardrobe_items(db_session, user_id)) == 2


def test_add_wardrobe_items_from_catalog_duplicate_id_in_one_batch(db_session):
    a = _add_catalog_item(db_session, category="top")
    user_id = uuid.uuid4()

    items = crud.add_wardrobe_items_from_catalog(db_session, user_id, [a.id, a.id])

    assert len(items) == 2
    assert items[0].id != items[1].id  # two independent rows, not deduplicated


def test_add_wardrobe_items_from_catalog_any_unknown_id_rejects_whole_batch(db_session):
    a = _add_catalog_item(db_session, category="top")
    user_id = uuid.uuid4()
    unknown_id = uuid.uuid4()

    try:
        crud.add_wardrobe_items_from_catalog(db_session, user_id, [a.id, unknown_id])
        assert False, "expected UnknownCatalogItemIds"
    except crud.UnknownCatalogItemIds as e:
        assert e.missing_ids == [unknown_id]

    assert crud.list_wardrobe_items(db_session, user_id) == []


# --- update_wardrobe_item (T026) ---------------------------------------------


def test_update_wardrobe_item_valid_correction_leaves_other_fields_unchanged(db_session):
    user_id = uuid.uuid4()
    row = _add_item(db_session, user_id, formality="casual", warmth=2, category="jeans")

    updated = crud.update_wardrobe_item(db_session, user_id, row.id, WardrobeItemPatch(formality="formal"))

    assert updated.formality == "formal"
    assert updated.warmth == 2
    assert updated.category == "jeans"


@pytest.mark.parametrize(
    "bad_kwargs",
    [
        {"formality": "extremely_fancy"},
        {"season": ["rainy"]},
        {"warmth": 9},
        {"warmth": -1},
        {"colors": ["notahex"]},
    ],
)
def test_update_wardrobe_item_invalid_constrained_field_rejected_at_construction(db_session, bad_kwargs):
    """FR-007: an invalid formality/season/warmth/colors value is rejected
    before it can ever reach update_wardrobe_item -- WardrobeItemPatch's own
    validators raise, exactly as FastAPI's request-body parsing would (422),
    so the item's prior value is never touched."""
    user_id = uuid.uuid4()
    _add_item(db_session, user_id, formality="casual", warmth=2)

    with pytest.raises(pydantic.ValidationError):
        WardrobeItemPatch(**bad_kwargs)

    closet = crud.list_wardrobe_items(db_session, user_id)
    assert closet[0].formality == "casual"
    assert closet[0].warmth == 2


def test_update_wardrobe_item_unrecognized_category_accepted(db_session):
    """Category is open-ended -- FR-007. Its slot/bucket falls back to
    'accessory' on read via categories.group_of(), not validated here."""
    user_id = uuid.uuid4()
    row = _add_item(db_session, user_id, category="top")

    updated = crud.update_wardrobe_item(db_session, user_id, row.id, WardrobeItemPatch(category="glorbtastic"))

    assert updated.category == "glorbtastic"


def test_update_wardrobe_item_accessory_category_item_works(db_session):
    """FR-005: correcting an accessory-category item works identically."""
    user_id = uuid.uuid4()
    row = _add_item(db_session, user_id, category="jewelry", formality="casual")

    updated = crud.update_wardrobe_item(db_session, user_id, row.id, WardrobeItemPatch(formality="formal"))

    assert updated.category == "jewelry"
    assert updated.formality == "formal"


def test_update_wardrobe_item_cross_user_returns_none(db_session):
    owner, other = uuid.uuid4(), uuid.uuid4()
    row = _add_item(db_session, owner, formality="casual")

    result = crud.update_wardrobe_item(db_session, other, row.id, WardrobeItemPatch(formality="formal"))

    assert result is None
    assert crud.list_wardrobe_items(db_session, owner)[0].formality == "casual"


def test_update_wardrobe_item_unknown_item_returns_none(db_session):
    assert (
        crud.update_wardrobe_item(db_session, uuid.uuid4(), uuid.uuid4(), WardrobeItemPatch(formality="formal")) is None
    )


# --- delete_wardrobe_item (T030) ---------------------------------------------


def test_delete_wardrobe_item_normal_delete(db_session):
    user_id = uuid.uuid4()
    row = _add_item(db_session, user_id)

    result = crud.delete_wardrobe_item(db_session, user_id, row.id)

    assert result is True
    assert crud.list_wardrobe_items(db_session, user_id) == []


def test_delete_wardrobe_item_repeated_delete_is_safe(db_session):
    user_id = uuid.uuid4()
    row = _add_item(db_session, user_id)

    first = crud.delete_wardrobe_item(db_session, user_id, row.id)
    second = crud.delete_wardrobe_item(db_session, user_id, row.id)

    assert first is True
    assert second is False  # already gone, not a crash


def test_delete_wardrobe_item_cross_user_delete_leaves_item_untouched(db_session):
    owner, other = uuid.uuid4(), uuid.uuid4()
    row = _add_item(db_session, owner)

    result = crud.delete_wardrobe_item(db_session, other, row.id)

    assert result is False
    assert len(crud.list_wardrobe_items(db_session, owner)) == 1


def test_delete_wardrobe_item_unknown_item_returns_false(db_session):
    assert crud.delete_wardrobe_item(db_session, uuid.uuid4(), uuid.uuid4()) is False


def test_delete_wardrobe_item_accessory_category_item_works(db_session):
    """FR-005: deleting an accessory-category item works identically."""
    user_id = uuid.uuid4()
    row = _add_item(db_session, user_id, category="jewelry")

    result = crud.delete_wardrobe_item(db_session, user_id, row.id)

    assert result is True
    assert crud.list_wardrobe_items(db_session, user_id) == []
