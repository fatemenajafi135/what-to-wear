"""SQLAlchemy ORM models — the persistence-layer mirror of `schema.py`'s
Pydantic `WardrobeItem` contract, not a second contract (constitution
Principle VII). Row classes are suffixed `Row` so they never shadow the
frozen Pydantic `WardrobeItem` when both are imported in `crud.py`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class CatalogItemRow(Base):
    """Shared, pre-built item definition. Read-only through the API; written
    only by the one-time seed step from data/fixtures/wardrobe.json."""

    __tablename__ = "catalog_items"
    __table_args__ = (CheckConstraint("warmth BETWEEN 0 AND 5", name="ck_catalog_items_warmth_range"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String, nullable=False)
    colors: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    fabric: Mapped[str | None] = mapped_column(String, nullable=True)
    warmth: Mapped[int] = mapped_column(nullable=False)
    formality: Mapped[str] = mapped_column(String, nullable=False)
    season: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)


class WardrobeItemRow(Base):
    """An item a specific user owns. One row per owned garment/accessory
    instance — adding the same catalog item twice creates two rows."""

    __tablename__ = "wardrobe_items"
    __table_args__ = (CheckConstraint("warmth BETWEEN 0 AND 5", name="ck_wardrobe_items_warmth_range"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # No FK — there is no local `users` table; user_id is a bare opaque UUID
    # from the verified JWT `sub` claim (research.md -> "no local users table").
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String, nullable=False)
    colors: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    fabric: Mapped[str | None] = mapped_column(String, nullable=True)
    warmth: Mapped[int] = mapped_column(nullable=False)
    formality: Mapped[str] = mapped_column(String, nullable=False)
    season: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="catalog")
    catalog_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("catalog_items.id"), nullable=True
    )
    # Additive, nullable (Feature 003) — catalog-sourced rows have neither.
    pattern: Mapped[str | None] = mapped_column(String, nullable=True)
    fit: Mapped[str | None] = mapped_column(String, nullable=True)
    # Additive, nullable (Feature 006) — catalog-sourced rows never have one.
    photo_path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)


class SuggestionFeedbackRow(Base):
    """A user's current reaction (liked/rejected) to one outfit, identified
    by its item set (Feature 004: preference-memory). At most one row per
    (user_id, item_ids_key) -- a later reaction to the same outfit replaces
    this row rather than adding a new one (spec.md Edge Cases).

    item_snapshot is a point-in-time copy of each item's category/colors/
    formality, not a live join to wardrobe_items -- a later edit or delete
    of the underlying item must not retroactively change historical
    feedback (specs/004-preference-memory/research.md ->
    "Reaction identity / de-dup key")."""

    __tablename__ = "suggestion_feedback"
    __table_args__ = (
        CheckConstraint("verdict IN ('liked','rejected')", name="ck_suggestion_feedback_verdict"),
        UniqueConstraint("user_id", "item_ids_key", name="uq_suggestion_feedback_user_items"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    verdict: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(String, nullable=True)
    item_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    # Sorted, comma-joined item_ids -- the plain-String half of the unique
    # dedup key, avoiding JSONB-equality edge cases (data-model.md).
    item_ids_key: Mapped[str] = mapped_column(String, nullable=False)
    item_snapshot: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)


class PreferenceSignalDismissalRow(Base):
    """Per-user, per-signal suppression cutoff (Feature 004). Not a
    materialized profile -- stores no derived value, only a timestamp
    cutoff: derive_signals() excludes feedback rows created at or before
    dismissed_at when computing this one signal_key. Upserted, not
    inserted-only -- "remove a signal" and "clear the whole profile" both
    just move this cutoff forward (research.md -> "Removing one signal /
    clearing the whole profile without a profile table")."""

    __tablename__ = "preference_signal_dismissal"
    __table_args__ = (UniqueConstraint("user_id", "signal_key", name="uq_pref_dismissal_user_signal"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    signal_key: Mapped[str] = mapped_column(String, nullable=False)
    dismissed_at: Mapped[datetime] = mapped_column(nullable=False)
