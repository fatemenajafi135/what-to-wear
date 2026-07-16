"""Direct CRUD functions over Postgres. No repository-pattern abstraction —
one concrete implementation, per the constitution's Quality Bar.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ingest.loaders import REPO_ROOT
from .memory import preferences
from .models import CatalogItemRow, PreferenceSignalDismissalRow, SuggestionFeedbackRow, WardrobeItemRow
from .schema import (
    CreateWardrobeItemFromUploadRequest,
    SubmitFeedbackRequest,
    SuggestionFeedback,
    WardrobeItem,
    WardrobeItemPatch,
)

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


class UnknownWardrobeItemIds(Exception):
    """Raised by record_feedback when one or more item_ids don't exist in
    the caller's own wardrobe_items -- either the id doesn't exist at all,
    or it belongs to a different user (never distinguished in the error,
    same as the rest of this codebase's not-found-vs-forbidden convention).
    Carries the offending ids for the caller (the API layer) to report back
    in a 404 (constitution Principle IV: a reaction can't be grounded in
    items the caller doesn't own)."""

    def __init__(self, missing_ids: list[uuid.UUID]) -> None:
        self.missing_ids = missing_ids
        super().__init__(f"unknown wardrobe item_id(s): {[str(i) for i in missing_ids]}")


def _utcnow() -> datetime:
    # Naive, UTC-by-convention -- matches how the rest of this codebase
    # reads back Postgres TIMESTAMP (no tz) columns (see WardrobeItemRow's
    # created_at/updated_at). Stripping tzinfo keeps comparisons against
    # those columns from raising "can't compare offset-naive and
    # offset-aware datetimes".
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
        pattern=getattr(row, "pattern", None),
        fit=getattr(row, "fit", None),
        photo_path=getattr(row, "photo_path", None),
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
        select(WardrobeItemRow).where(WardrobeItemRow.user_id == user_uuid).order_by(WardrobeItemRow.created_at.desc())
    ).all()
    return [_to_wardrobe_item(r) for r in rows]


def update_wardrobe_item(
    session: Session, user_id: str | uuid.UUID, item_id: str | uuid.UUID, patch: WardrobeItemPatch
) -> WardrobeItem | None:
    """Applies only the fields present in `patch` (PATCH semantics) to an
    owned item. Returns None if the item doesn't exist or isn't owned by
    `user_id` -- treated as not-found either way, not forbidden (spec Edge
    Cases). `patch`'s own validators already rejected any invalid constrained
    value before this is ever called (FR-007), so nothing here can fail on
    the DB CHECK constraint."""
    try:
        item_uuid, user_uuid = uuid.UUID(str(item_id)), uuid.UUID(str(user_id))
    except ValueError:
        return None
    row = session.get(WardrobeItemRow, item_uuid)
    if row is None or row.user_id != user_uuid:
        return None
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    session.commit()
    return _to_wardrobe_item(row)


def delete_wardrobe_item(session: Session, user_id: str | uuid.UUID, item_id: str | uuid.UUID) -> bool:
    """Hard delete. Returns True if a row was actually deleted, False if it
    didn't exist, wasn't owned by `user_id`, or was already removed -- the
    caller maps False to 404. A second delete or a cross-user delete is
    "already gone," not a crash (spec Edge Cases)."""
    try:
        item_uuid, user_uuid = uuid.UUID(str(item_id)), uuid.UUID(str(user_id))
    except ValueError:
        return False
    row = session.get(WardrobeItemRow, item_uuid)
    if row is None or row.user_id != user_uuid:
        return False
    session.delete(row)
    session.commit()
    return True


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


def create_wardrobe_item_from_upload(
    session: Session, user_id: str | uuid.UUID, req: CreateWardrobeItemFromUploadRequest
) -> WardrobeItem:
    """Persists a wardrobe item from user-confirmed photo-extraction
    attributes. source='upload', no catalog_item_id -- parallel to, not
    replacing, add_wardrobe_item_from_catalog (US2)."""
    row = WardrobeItemRow(
        user_id=uuid.UUID(str(user_id)),
        category=req.category,
        colors=req.colors,
        fabric=req.fabric,
        warmth=req.warmth,
        formality=req.formality,
        season=req.season,
        pattern=req.pattern,
        fit=req.fit,
        photo_path=req.photo_path,
        source="upload",
        catalog_item_id=None,
    )
    session.add(row)
    session.commit()
    return _to_wardrobe_item(row)


def _item_ids_key(item_ids: list[str]) -> str:
    return ",".join(sorted(item_ids))


def _to_suggestion_feedback(row: SuggestionFeedbackRow) -> SuggestionFeedback:
    return SuggestionFeedback(
        id=str(row.id),
        verdict=row.verdict,
        reason=row.reason,
        item_ids=row.item_ids,
        created_at=row.created_at.isoformat(),
    )


def record_feedback(session: Session, user_id: str | uuid.UUID, req: SubmitFeedbackRequest) -> SuggestionFeedback:
    """Records (or replaces) a reaction to a specific outfit, identified by
    its item set (specs/004-preference-memory/research.md #1). item_ids are
    resolved against the caller's own wardrobe_items -- never trusted as-is
    (constitution Principle IV, grounded output) -- and snapshotted at their
    current attributes, since a later edit/delete of the item must not
    retroactively change historical feedback. Upserts on (user_id,
    item_ids_key): a later reaction to the same outfit replaces the earlier
    one rather than accumulating (spec.md Edge Cases)."""
    user_uuid = uuid.UUID(str(user_id))
    item_uuids = [uuid.UUID(str(i)) for i in req.item_ids]
    rows = {
        row.id: row
        for row in session.scalars(
            select(WardrobeItemRow).where(WardrobeItemRow.id.in_(item_uuids), WardrobeItemRow.user_id == user_uuid)
        )
    }
    missing = [i for i in item_uuids if i not in rows]
    if missing:
        raise UnknownWardrobeItemIds(missing)

    item_ids_key = _item_ids_key(req.item_ids)
    snapshot = [
        {
            "item_id": str(rows[i].id),
            "category": rows[i].category,
            "colors": rows[i].colors,
            "formality": rows[i].formality,
        }
        for i in item_uuids
    ]

    existing = session.scalar(
        select(SuggestionFeedbackRow).where(
            SuggestionFeedbackRow.user_id == user_uuid, SuggestionFeedbackRow.item_ids_key == item_ids_key
        )
    )
    if existing is not None:
        existing.verdict = req.verdict
        existing.reason = req.reason
        existing.item_snapshot = snapshot
        # created_at's onupdate=func.now() fires automatically on this
        # UPDATE -- an updated reaction is "created now" for dedup/recency
        # purposes (data-model.md).
        session.commit()
        return _to_suggestion_feedback(existing)

    row = SuggestionFeedbackRow(
        user_id=user_uuid,
        verdict=req.verdict,
        reason=req.reason,
        item_ids=sorted(req.item_ids),
        item_ids_key=item_ids_key,
        item_snapshot=snapshot,
    )
    session.add(row)
    session.commit()
    return _to_suggestion_feedback(row)


def _to_feedback_record(row: SuggestionFeedbackRow) -> preferences.FeedbackRecord:
    return preferences.FeedbackRecord(
        verdict=row.verdict,
        item_snapshot=[preferences.ItemSnapshot(**item) for item in row.item_snapshot],
        created_at=row.created_at,
    )


def get_derivation_inputs(
    session: Session, user_id: str | uuid.UUID
) -> tuple[list[preferences.FeedbackRecord], dict[str, datetime]]:
    """Raw materials for preferences.derive_signals(), converted from ORM
    rows to that module's plain dataclasses. Both memory.store.get_profile()
    (feeds profile_note()) and the /preferences endpoints call this, so
    every surface derives from the exact same data (data-model.md)."""
    user_uuid = uuid.UUID(str(user_id))
    feedback_rows = session.scalars(
        select(SuggestionFeedbackRow).where(SuggestionFeedbackRow.user_id == user_uuid)
    ).all()
    dismissal_rows = session.scalars(
        select(PreferenceSignalDismissalRow).where(PreferenceSignalDismissalRow.user_id == user_uuid)
    ).all()
    feedback = [_to_feedback_record(row) for row in feedback_rows]
    dismissals = {row.signal_key: row.dismissed_at for row in dismissal_rows}
    return feedback, dismissals


def has_any_feedback(session: Session, user_id: str | uuid.UUID) -> bool:
    """Distinguishes "no feedback at all" (FR-008's empty state) from
    "feedback exists but no signal has crossed threshold yet" -- both
    project to an empty signals list, but only the former is has_feedback=False."""
    user_uuid = uuid.UUID(str(user_id))
    return (
        session.scalar(select(SuggestionFeedbackRow.id).where(SuggestionFeedbackRow.user_id == user_uuid).limit(1))
        is not None
    )


def dismiss_signal(session: Session, user_id: str | uuid.UUID, signal_key: str) -> None:
    """Upserts a dismissal cutoff for one signal_key. "Remove a signal" and
    "clear the whole profile" (which calls this once per currently-present
    key) share this one mechanism -- research.md #3."""
    user_uuid = uuid.UUID(str(user_id))
    existing = session.scalar(
        select(PreferenceSignalDismissalRow).where(
            PreferenceSignalDismissalRow.user_id == user_uuid,
            PreferenceSignalDismissalRow.signal_key == signal_key,
        )
    )
    now = _utcnow()
    if existing is not None:
        existing.dismissed_at = now
    else:
        session.add(PreferenceSignalDismissalRow(user_id=user_uuid, signal_key=signal_key, dismissed_at=now))
    session.commit()


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
        session.scalar(select(WardrobeItemRow.id).where(WardrobeItemRow.user_id == EVAL_BASELINE_USER_ID).limit(1))
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
