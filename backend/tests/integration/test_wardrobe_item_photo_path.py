"""Integration test for Feature 006 (wardrobe-item-photos): photo_path
persists through create_wardrobe_item_from_upload and round-trips via
list_wardrobe_items; catalog-sourced items never have one. Pure DB
round-trip, no LLM calls -- uses the db_session rollback-isolation
fixture, not the non-isolated pattern that caused a real bug during the
005 merge (see docs/005-production-hardening-merge-report.md)."""

from __future__ import annotations

import uuid

from whattowear import crud
from whattowear.models import CatalogItemRow
from whattowear.schema import CreateWardrobeItemFromUploadRequest


def test_photo_path_round_trips_for_uploaded_item(db_session):
    user_id = uuid.uuid4()
    req = CreateWardrobeItemFromUploadRequest(
        photo_path="user/abc-shirt.jpg",
        category="top",
        colors=["#1b2a4a"],
        formality="smart_casual",
        warmth=2,
        season=["spring"],
        fabric="cotton",
        pattern="solid",
        fit="regular",
    )

    created = crud.create_wardrobe_item_from_upload(db_session, user_id, req)
    assert created.photo_path == "user/abc-shirt.jpg"

    closet = crud.list_wardrobe_items(db_session, user_id)
    assert len(closet) == 1
    assert closet[0].photo_path == "user/abc-shirt.jpg"


def test_photo_path_is_none_for_catalog_sourced_item(db_session):
    catalog_row = CatalogItemRow(category="top", colors=["#ffffff"], formality="casual", warmth=1, season=["summer"])
    db_session.add(catalog_row)
    db_session.commit()
    user_id = uuid.uuid4()

    item = crud.add_wardrobe_item_from_catalog(db_session, user_id, catalog_row.id)

    assert item.photo_path is None
