"""Database-backed `ports.ClosetRepository` — the real implementation feature
004 adds alongside (not instead of) `adapters.closet_fixture.
FixtureClosetRepository`. Together they're the two concrete implementations
the constitution's Quality Bar asks for before `ports.py`'s Protocol is
justified.

Every query filters by `user_id` explicitly — that filter, not the RLS
policy on `wardrobe_items`, is the actual isolation guarantee for this
backend's own traffic, because the pooler role this app connects as has
BYPASSRLS (specs/004-closet-read/research.md §1). Each per-user query is
still preceded by setting `request.jwt.claim.sub` in the same transaction:
inert today given the bypass role, but correct and forward-compatible with
the convention `0001_init.sql` documents, and free.

`get_derivation_inputs` always returns `([], {})` — preference/feedback
derivation data doesn't exist yet (feature 010's territory), matching
`FixtureClosetRepository`'s own documented behavior exactly.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from ..core.db import get_session
from ..schema import WardrobeItem

if TYPE_CHECKING:
    from ..memory.preferences import FeedbackRecord

# `get_session` is written as a single-yield generator with a try/finally —
# exactly the shape `@contextmanager` expects — so it's reused as a plain
# context manager here rather than duplicating session lifecycle handling.
_session_scope = contextmanager(get_session)

# Both tables share every one of these columns except `source`, which only
# exists on `wardrobe_items` — the catalog query below projects a literal
# `'catalog'` in its place so both queries can share one row->model mapping.
_ITEM_COLUMNS = "id, category, colors, formality, warmth, season, fabric, pattern, fit, name, notes, source, photo_path"


def _row_to_wardrobe_item(row: Row[Any]) -> WardrobeItem:
    m = row._mapping
    return WardrobeItem(
        id=str(m["id"]),
        category=m["category"],
        colors=list(m["colors"] or []),
        formality=m["formality"],
        warmth=m["warmth"],
        season=list(m["season"] or []),
        fabric=m["fabric"],
        source=m["source"],
        pattern=m["pattern"],
        fit=m["fit"],
        photo_path=m["photo_path"],
        name=m["name"],
        notes=m["notes"],
    )


def _set_jwt_claim(session: Session, user_id: str) -> None:
    session.execute(text("SELECT set_config('request.jwt.claim.sub', :user_id, true)"), {"user_id": user_id})


class SupabaseClosetRepository:
    """Satisfies `ports.ClosetRepository` against real Postgres."""

    def list_wardrobe_items(self, user_id: str) -> list[WardrobeItem]:
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            rows = session.execute(
                text(f"SELECT {_ITEM_COLUMNS} FROM wardrobe_items WHERE user_id = :user_id"),
                {"user_id": user_id},
            ).fetchall()
            return [_row_to_wardrobe_item(row) for row in rows]

    def list_catalog_items(self) -> list[WardrobeItem]:
        with _session_scope() as session:
            columns = _ITEM_COLUMNS.replace("source", "'catalog' AS source")
            rows = session.execute(text(f"SELECT {columns} FROM catalog_items")).fetchall()
            return [_row_to_wardrobe_item(row) for row in rows]

    def get_derivation_inputs(self, user_id: str) -> tuple[list[FeedbackRecord], dict[str, datetime]]:
        return [], {}

    def get_wardrobe_item(self, user_id: str, item_id: str) -> WardrobeItem | None:
        """Not part of `ports.ClosetRepository` — Protocols are structural,
        so a concrete class may expose extra methods beyond what it's
        required to satisfy. The item-detail route uses this single-row,
        indexed lookup instead of fetching the full wardrobe and filtering
        in Python (specs/004-closet-read/research.md §6)."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text(f"SELECT {_ITEM_COLUMNS} FROM wardrobe_items WHERE user_id = :user_id AND id = :item_id"),
                {"user_id": user_id, "item_id": item_id},
            ).fetchone()
            return _row_to_wardrobe_item(row) if row is not None else None
