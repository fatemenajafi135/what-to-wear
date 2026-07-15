"""Direct CRUD functions over Postgres. No repository-pattern abstraction —
one concrete implementation, per the constitution's Quality Bar.
"""

from __future__ import annotations

import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ingest.loaders import REPO_ROOT
from .models import CatalogItemRow, WardrobeItemRow
from .schema import WardrobeItem

WARDROBE_FIXTURE = REPO_ROOT / "data" / "fixtures" / "wardrobe.json"

# Fixed, well-known user_id for the eval harness's baseline closet. Derived
# deterministically (uuid5, not random) so every environment seeds the same
# id without coordinating a literal constant by hand.
EVAL_BASELINE_USER_ID = uuid.uuid5(uuid.NAMESPACE_URL, "whattowear:eval-baseline-user")


def _load_fixture_items() -> list[dict]:
    with open(WARDROBE_FIXTURE, encoding="utf-8") as fh:
        return json.load(fh)


class UnknownCatalogItemIds(Exception):
    """Raised by add_wardrobe_items_from_catalog when one or more requested
    catalog_item_ids don't exist. Carries the offending ids for the caller
    (the API layer) to report back in a 404."""

    def __init__(self, missing_ids: list[uuid.UUID]) -> None:
        self.missing_ids = missing_ids
        super().__init__(f"unknown catalog_item_id(s): {[str(i) for i in missing_ids]}")


def _to_wardrobe_item(row: WardrobeItemRow | CatalogItemRow) -> WardrobeItem:
    return WardrobeItem(
        id=str(row.id),
        category=row.category,
        colors=row.colors,
        formality=row.formality,
        warmth=row.warmth,
        season=row.season,
        fabric=row.fabric,
        source=getattr(row, "source", None),
    )


def list_wardrobe_items(session: Session, user_id: str | uuid.UUID) -> list[WardrobeItem]:
    """Every item in `user_id`'s closet, newest first. Empty closet -> [].

    `user_id` isn't always guaranteed to be a well-formed UUID at this call
    site: /wardrobe/items always passes one (verified JWT `sub` claim), but
    the older /recommend test endpoint accepts an arbitrary free-form string.
    A malformed id can't own any wardrobe rows, so it degrades to [] rather
    than raising -- a persistence-layer detail shouldn't crash the caller."""
    try:
        user_uuid = uuid.UUID(str(user_id))
    except ValueError:
        return []
    rows = session.scalars(
        select(WardrobeItemRow)
        .where(WardrobeItemRow.user_id == user_uuid)
        .order_by(WardrobeItemRow.created_at.desc())
    ).all()
    return [_to_wardrobe_item(r) for r in rows]


def list_catalog_items(session: Session) -> list[WardrobeItem]:
    """The shared, read-only catalog. Empty catalog -> [] (FR-010)."""
    rows = session.scalars(select(CatalogItemRow).order_by(CatalogItemRow.category)).all()
    return [_to_wardrobe_item(r) for r in rows]


def _wardrobe_row_from_catalog_row(user_id: uuid.UUID, catalog_row: CatalogItemRow) -> WardrobeItemRow:
    """A new, independent wardrobe_items row copying a catalog row's
    attributes (FR-011: a copy, not a live reference)."""
    return WardrobeItemRow(
        user_id=user_id,
        category=catalog_row.category,
        colors=catalog_row.colors,
        fabric=catalog_row.fabric,
        warmth=catalog_row.warmth,
        formality=catalog_row.formality,
        season=catalog_row.season,
        source="catalog",
        catalog_item_id=catalog_row.id,
    )


def add_wardrobe_item_from_catalog(
    session: Session, user_id: str | uuid.UUID, catalog_item_id: str | uuid.UUID
) -> WardrobeItem | None:
    """Copies a catalog item's attributes into a new wardrobe_items row.
    Returns None if catalog_item_id doesn't exist (caller -> 404)."""
    catalog_row = session.get(CatalogItemRow, uuid.UUID(str(catalog_item_id)))
    if catalog_row is None:
        return None
    row = _wardrobe_row_from_catalog_row(uuid.UUID(str(user_id)), catalog_row)
    session.add(row)
    session.commit()
    return _to_wardrobe_item(row)


def add_wardrobe_items_from_catalog(
    session: Session, user_id: str | uuid.UUID, catalog_item_ids: list[str | uuid.UUID]
) -> list[WardrobeItem]:
    """Bulk variant of add_wardrobe_item_from_catalog — one independent copy
    per listed id, duplicates allowed. All-or-nothing: raises
    UnknownCatalogItemIds (no rows inserted) if any id doesn't exist,
    rather than partially populating the closet."""
    ids = [uuid.UUID(str(i)) for i in catalog_item_ids]
    catalog_rows = {row.id: row for row in session.scalars(select(CatalogItemRow).where(CatalogItemRow.id.in_(ids)))}
    missing = [i for i in ids if i not in catalog_rows]
    if missing:
        raise UnknownCatalogItemIds(missing)

    user_uuid = uuid.UUID(str(user_id))
    rows = [_wardrobe_row_from_catalog_row(user_uuid, catalog_rows[i]) for i in ids]
    session.add_all(rows)
    session.commit()
    return [_to_wardrobe_item(r) for r in rows]


def seed_catalog(session: Session) -> int:
    """Load data/fixtures/wardrobe.json into catalog_items. Idempotent: a
    no-op if the catalog already has rows. Returns the number inserted."""
    already_seeded = session.scalar(select(CatalogItemRow.id).limit(1)) is not None
    if already_seeded:
        return 0
    rows = [
        CatalogItemRow(
            category=item["category"],
            colors=item["colors"],
            fabric=item.get("fabric"),
            warmth=item["warmth"],
            formality=item["formality"],
            season=item["season"],
        )
        for item in _load_fixture_items()
    ]
    session.add_all(rows)
    session.commit()
    return len(rows)


def seed_eval_baseline_user(session: Session) -> int:
    """Seed EVAL_BASELINE_USER_ID's wardrobe_items with the same 40 fixture
    items (source='catalog'), so the eval harness's no-regression gate reads
    an equivalent closet to the old fixture-based run. Idempotent: a no-op
    if that user already has rows. Seeds closet items only — no memory
    preferences — so memory.profile_note() stays None and generation
    behavior matches today's fixture-based runs exactly."""
    already_seeded = (
        session.scalar(
            select(WardrobeItemRow.id).where(WardrobeItemRow.user_id == EVAL_BASELINE_USER_ID).limit(1)
        )
        is not None
    )
    if already_seeded:
        return 0
    rows = [
        WardrobeItemRow(
            user_id=EVAL_BASELINE_USER_ID,
            category=item["category"],
            colors=item["colors"],
            fabric=item.get("fabric"),
            warmth=item["warmth"],
            formality=item["formality"],
            season=item["season"],
            source="catalog",
        )
        for item in _load_fixture_items()
    ]
    session.add_all(rows)
    session.commit()
    return len(rows)


if __name__ == "__main__":
    import argparse

    from .db import SessionLocal

    ap = argparse.ArgumentParser(description="One-time seed commands (see quickstart.md)")
    ap.add_argument("command", choices=["seed-catalog", "seed-eval-baseline"])
    args = ap.parse_args()

    with SessionLocal() as db_session:
        n = seed_catalog(db_session) if args.command == "seed-catalog" else seed_eval_baseline_user(db_session)
        print(f"{args.command}: inserted {n} row(s)")
