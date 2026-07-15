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
    """Every item in `user_id`'s closet, newest first. Empty closet -> []."""
    rows = session.scalars(
        select(WardrobeItemRow)
        .where(WardrobeItemRow.user_id == uuid.UUID(str(user_id)))
        .order_by(WardrobeItemRow.created_at.desc())
    ).all()
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
