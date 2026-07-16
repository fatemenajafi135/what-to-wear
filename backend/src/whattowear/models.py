"""SQLAlchemy ORM models — the persistence-layer mirror of `schema.py`'s
Pydantic `WardrobeItem` contract, not a second contract (constitution
Principle VII). Row classes are suffixed `Row` so they never shadow the
frozen Pydantic `WardrobeItem` when both are imported in `crud.py`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String
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
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)
