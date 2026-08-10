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
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import text
from sqlalchemy.engine import CursorResult, Row
from sqlalchemy.orm import Session

from ..core.db import get_session
from ..schema import CreateWardrobeItemFromUploadRequest, WardrobeItem, WardrobeItemPatch

if TYPE_CHECKING:
    from ..memory.preferences import FeedbackRecord


# `get_session` is written as a single-yield generator with a try/finally —
# exactly the shape `@contextmanager` expects — so it's reused as a plain
# context manager here rather than duplicating session lifecycle handling.
_session_scope = contextmanager(get_session)

# Both tables share every one of these columns except `source`, `favorite`,
# `photo_background_color`, and `isolated_photo_path`, which only exist on
# `wardrobe_items` (added by migrations 0008 and 0013 respectively, never
# backfilled onto `catalog_items` — shared/read-only stock photos were never
# in scope for a per-item backdrop colour or isolation) — the catalog query
# below projects literal `'catalog'`/`false`/`NULL` in their place so both
# queries can share one row->model mapping.
_ITEM_COLUMNS = (
    "id, category, colors, formality, warmth, season, fabric, pattern, fit, name, notes, source, photo_path, "
    "isolated_photo_path, photo_background_color, favorite"
)


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
        isolated_photo_path=m["isolated_photo_path"],
        photo_background_color=m["photo_background_color"],
        name=m["name"],
        notes=m["notes"],
        favorite=m["favorite"],
    )


def _set_jwt_claim(session: Session, user_id: str) -> None:
    session.execute(text("SELECT set_config('request.jwt.claim.sub', :user_id, true)"), {"user_id": user_id})


def _build_set_clause(fields: dict[str, Any]) -> str:
    # Keys come only from `WardrobeItemPatch`'s own field names (a fixed,
    # schema-defined set), never from unvalidated user input — safe to
    # interpolate directly into the SQL text.
    return ", ".join(f"{column} = :{column}" for column in fields)


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
            columns = (
                _ITEM_COLUMNS.replace("source", "'catalog' AS source")
                .replace("favorite", "false AS favorite")
                .replace("isolated_photo_path", "NULL AS isolated_photo_path")
                .replace("photo_background_color", "NULL AS photo_background_color")
            )
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

    def update_wardrobe_item(self, user_id: str, item_id: str, patch: WardrobeItemPatch) -> WardrobeItem | None:
        """Partial update — feature 005. Only fields present on `patch`
        (`exclude_unset`) are written, matching `WardrobeItemPatch`'s own
        PATCH-semantics doc comment. A patch with nothing set skips the
        `UPDATE` entirely (an empty `SET` clause is invalid SQL) and just
        re-fetches, so a no-op call still returns the current row — or
        `None` if it doesn't belong to `user_id`."""
        fields = patch.model_dump(exclude_unset=True)
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            if fields:
                session.execute(
                    text(
                        f"UPDATE wardrobe_items SET {_build_set_clause(fields)} "
                        "WHERE user_id = :user_id AND id = :item_id"
                    ),
                    {**fields, "user_id": user_id, "item_id": item_id},
                )
                session.commit()
            row = session.execute(
                text(f"SELECT {_ITEM_COLUMNS} FROM wardrobe_items WHERE user_id = :user_id AND id = :item_id"),
                {"user_id": user_id, "item_id": item_id},
            ).fetchone()
            return _row_to_wardrobe_item(row) if row is not None else None

    def toggle_favorite(self, user_id: str, item_id: str) -> bool | None:
        """Reads-then-flips in one statement (`RETURNING`) rather than a
        separate read + write — the client has no reliable local copy of
        the current value to flip and round-trip, since Item detail never
        displays it (design-system §2.3). Returns the value *after* the
        toggle, or `None` if the item doesn't belong to `user_id`."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text(
                    "UPDATE wardrobe_items SET favorite = NOT favorite "
                    "WHERE user_id = :user_id AND id = :item_id "
                    "RETURNING favorite"
                ),
                {"user_id": user_id, "item_id": item_id},
            ).fetchone()
            session.commit()
            return bool(row._mapping["favorite"]) if row is not None else None

    def record_wear(self, user_id: str, item_id: str) -> bool:
        """Idempotent per calendar day (docs/design-decisions.md §22.1): a
        second call the same day no-ops against `item_wears`' own
        `(item_id, worn_date)` unique constraint rather than inserting a
        second row. Returns `False` if the item doesn't belong to
        `user_id` (or doesn't exist); `True` otherwise, whether this call
        inserted a new row or matched an existing one for today."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            owned = session.execute(
                text("SELECT 1 FROM wardrobe_items WHERE user_id = :user_id AND id = :item_id"),
                {"user_id": user_id, "item_id": item_id},
            ).fetchone()
            if owned is None:
                return False
            session.execute(
                text(
                    "INSERT INTO item_wears (item_id, user_id, worn_date) "
                    "VALUES (:item_id, :user_id, CURRENT_DATE) "
                    "ON CONFLICT (item_id, worn_date) DO NOTHING"
                ),
                {"item_id": item_id, "user_id": user_id},
            )
            session.commit()
            return True

    def create_wardrobe_item_from_upload(
        self, user_id: str, request: CreateWardrobeItemFromUploadRequest
    ) -> WardrobeItem:
        """Feature 006. Not part of `ports.ClosetRepository` — same reason
        the four write methods above aren't (handoff trap 5): the AI
        pipeline's Protocol stays exactly as feature 007 defined it.
        `formality`/`warmth`/`season` are required by the request model and
        inserted as given — no defaulting. They used to fall back to
        module-level constants when omitted, which meant every photo-added
        item stored `casual`/`3`/all-four-seasons no matter what the VLM had
        detected (design-decisions.md §30). `fabric`/`pattern`/`fit` insert
        as `NULL` when omitted, matching the database's own nullability —
        an honest "not supplied" rather than an invented value.
        `isolated_photo_path` (feature 018) inserts unmodified — this
        method does not re-attempt isolation or re-validate the path
        beyond the route's own ownership-prefix check (spec.md FR-013)."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text(
                    "INSERT INTO wardrobe_items "
                    "(user_id, category, colors, formality, warmth, season, fabric, pattern, fit, "
                    "name, notes, photo_path, isolated_photo_path, photo_background_color, source) "
                    "VALUES (:user_id, :category, :colors, :formality, :warmth, :season, :fabric, "
                    ":pattern, :fit, :name, :notes, :photo_path, :isolated_photo_path, "
                    ":photo_background_color, 'upload') "
                    f"RETURNING {_ITEM_COLUMNS}"
                ),
                {
                    "user_id": user_id,
                    "category": request.category,
                    "colors": request.colors,
                    "formality": request.formality,
                    "warmth": request.warmth,
                    "season": request.season,
                    "fabric": request.fabric,
                    "pattern": request.pattern,
                    "fit": request.fit,
                    "name": request.name,
                    "notes": request.notes,
                    "photo_path": request.photo_path,
                    "isolated_photo_path": request.isolated_photo_path,
                    "photo_background_color": request.photo_background_color,
                },
            ).fetchone()
            session.commit()
            assert row is not None
            return _row_to_wardrobe_item(row)

    def delete_wardrobe_item(self, user_id: str, item_id: str) -> bool:
        """Hard delete — cascades to the item's `item_wears` rows via the
        migration's `on delete cascade`. Returns whether a row was
        actually removed, so the route can 404 identically whether the
        item never existed or belongs to someone else."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            result = cast(
                "CursorResult[Any]",
                session.execute(
                    text("DELETE FROM wardrobe_items WHERE user_id = :user_id AND id = :item_id"),
                    {"user_id": user_id, "item_id": item_id},
                ),
            )
            session.commit()
            return result.rowcount > 0
