"""Database-backed persistence for saved outfits (feature 009,
specs/009-suggestion-pager/data-model.md; extended by feature 010,
specs/010-outfits/data-model.md).

The project's first outfit persistence — before 009, a suggestion existed
only inside one HTTP response. Mirrors `supabase_closet.py`'s session/JWT-
claim pattern exactly: `request.jwt.claim.sub` is set per transaction for
the same forward-compatibility reason (the pooler role has BYPASSRLS today,
so the query-level `WHERE user_id = ...` is the real isolation guarantee for
this backend's own traffic; the outfits table's own RLS + GRANT is defense-
in-depth for any other access path — see infra/supabase/migrations/
0009_outfits.sql / 0010_outfits_detail.sql).
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Literal, cast

from sqlalchemy import text
from sqlalchemy.engine import CursorResult, Row
from sqlalchemy.orm import Session

from ..core.db import get_session

_session_scope = contextmanager(get_session)

# Every column `get`/`list` project back to the route, in table order —
# shared so both queries stay in sync with the table's real shape rather
# than two independently-maintained column lists drifting apart.
_OUTFIT_COLUMNS = (
    "id, title, occasion, meta_line, rationale_text, rationale_with_citations, citations, "
    "dimension_scores, match_label, item_ids, favorite, created_at"
)

Sort = Literal["date", "favorite", "most_worn"]

_ORDER_BY: dict[Sort, str] = {
    "date": "o.created_at DESC",
    "favorite": "o.favorite DESC, o.created_at DESC",
    # `outfit_wears` is joined, not read from a denormalized counter column
    # on `outfits` itself — see design-decisions.md §39/§41: a first-class
    # per-day wear table is the only way to answer "most worn" without a
    # made-up aggregation rule.
    "most_worn": "COALESCE(w.wear_count, 0) DESC, o.created_at DESC",
}


def _set_jwt_claim(session: Session, user_id: str) -> None:
    session.execute(text("SELECT set_config('request.jwt.claim.sub', :user_id, true)"), {"user_id": user_id})


class SupabaseOutfitRepository:
    def create(
        self,
        user_id: str,
        occasion: str,
        meta_line: str,
        rationale_text: str,
        match_label: str,
        item_ids: list[str],
        title: str,
        rationale_with_citations: str = "",
        citations: list[dict[str, Any]] | None = None,
        dimension_scores: list[dict[str, Any]] | None = None,
        thread_id: str | None = None,
    ) -> str:
        """`title`, `rationale_with_citations`, `citations`, and
        `dimension_scores` are feature 010 additions (design-decisions.md
        §38) — the caller (the save route) is responsible for resolving
        them from the pipeline's checkpointed thread state before calling
        this, or passing the empty/seeded defaults when that state isn't
        available. `citations`/`dimension_scores` default to `None` rather
        than `[]` as a mutable-default-argument safeguard; treated as empty
        either way. `thread_id` is a feature 011 addition (design-decisions.md
        §45) — the caller already has it in scope at the moment it saves
        each outfit; `None` only for call sites that predate this feature,
        which none of this codebase's own callers are anymore."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text(
                    "INSERT INTO outfits (user_id, occasion, meta_line, rationale_text, match_label, item_ids, "
                    "title, rationale_with_citations, citations, dimension_scores, thread_id) "
                    "VALUES (:user_id, :occasion, :meta_line, :rationale_text, :match_label, :item_ids, "
                    ":title, :rationale_with_citations, CAST(:citations AS jsonb), "
                    "CAST(:dimension_scores AS jsonb), :thread_id) "
                    "RETURNING id"
                ),
                {
                    "user_id": user_id,
                    "occasion": occasion,
                    "meta_line": meta_line,
                    "rationale_text": rationale_text,
                    "match_label": match_label,
                    "item_ids": item_ids,
                    "title": title,
                    "rationale_with_citations": rationale_with_citations,
                    "citations": json.dumps(citations or []),
                    "dimension_scores": json.dumps(dimension_scores or []),
                    "thread_id": thread_id,
                },
            ).fetchone()
            session.commit()
            assert row is not None
            return str(row._mapping["id"])

    def toggle_favorite(self, user_id: str, outfit_id: str) -> bool | None:
        """Same read-then-flip-in-one-statement shape as
        `supabase_closet.py::toggle_favorite` — returns the value *after* the
        toggle, or `None` if the row doesn't belong to `user_id`."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text(
                    "UPDATE outfits SET favorite = NOT favorite "
                    "WHERE user_id = :user_id AND id = :outfit_id "
                    "RETURNING favorite"
                ),
                {"user_id": user_id, "outfit_id": outfit_id},
            ).fetchone()
            session.commit()
            return bool(row._mapping["favorite"]) if row is not None else None

    def list_outfits(self, user_id: str, sort: Sort = "date") -> list[Row[Any]]:
        """The gallery's own query — feature 010. Named `list_outfits`, not
        `list`, matching `supabase_closet.py`'s own `list_wardrobe_items`/
        `list_catalog_items` convention — a bare `list` also shadows the
        builtin inside every other method's `list[...]` annotations in this
        same class body under `from __future__ import annotations`, which
        mypy flags. Joins a per-outfit wear count only when `sort ==
        "most_worn"` needs it (the join is cheap either way at this table's
        expected size, but the explicit `_ORDER_BY` mapping keeps the SQL
        text itself the single source of truth for what each sort value
        means, rather than branching in Python)."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            rows = session.execute(
                text(
                    f"SELECT o.id, o.title, o.match_label, o.favorite, o.created_at, o.item_ids "
                    "FROM outfits o "
                    "LEFT JOIN (SELECT outfit_id, COUNT(*) AS wear_count FROM outfit_wears GROUP BY outfit_id) w "
                    "ON w.outfit_id = o.id "
                    "WHERE o.user_id = :user_id "
                    f"ORDER BY {_ORDER_BY[sort]}"
                ),
                {"user_id": user_id},
            ).fetchall()
            return list(rows)

    def get(self, user_id: str, outfit_id: str) -> Row[Any] | None:
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text(f"SELECT {_OUTFIT_COLUMNS} FROM outfits WHERE user_id = :user_id AND id = :outfit_id"),
                {"user_id": user_id, "outfit_id": outfit_id},
            ).fetchone()
            return row

    def delete(self, user_id: str, outfit_id: str) -> bool:
        """Hard delete (design-decisions.md §40 — confirmation is a
        client-side UI gate, not a second server-side step, matching
        `delete_wardrobe_item`'s own shape). Cascades to the outfit's
        `outfit_wears` rows via the migration's `on delete cascade`."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            result = cast(
                "CursorResult[Any]",
                session.execute(
                    text("DELETE FROM outfits WHERE user_id = :user_id AND id = :outfit_id"),
                    {"user_id": user_id, "outfit_id": outfit_id},
                ),
            )
            session.commit()
            return result.rowcount > 0

    def rename(self, user_id: str, outfit_id: str, title: str) -> str | None:
        """The route validates `title` is non-empty/non-whitespace before
        calling this — this method trusts its caller, matching this file's
        existing division of concerns (routes validate request shape,
        repositories don't re-validate)."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text("UPDATE outfits SET title = :title WHERE user_id = :user_id AND id = :outfit_id RETURNING title"),
                {"user_id": user_id, "outfit_id": outfit_id, "title": title},
            ).fetchone()
            session.commit()
            return str(row._mapping["title"]) if row is not None else None

    def log_worn(self, user_id: str, outfit_id: str, owned_item_ids: list[str]) -> bool:
        """design-decisions.md §39: logs the outfit itself as worn today
        AND every item in `owned_item_ids` (the route pre-filters
        `outfit.item_ids` down to ones the caller currently owns — this
        method trusts that filtering already happened, same
        route-validates/repository-trusts split as `rename` above). Both
        writes share one transaction; each is independently idempotent per
        calendar day via its own `ON CONFLICT ... DO NOTHING`, so a retried
        call after a partial failure is always safe. Returns `False`
        without writing anything if `outfit_id` doesn't belong to
        `user_id`."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            owned = session.execute(
                text("SELECT 1 FROM outfits WHERE user_id = :user_id AND id = :outfit_id"),
                {"user_id": user_id, "outfit_id": outfit_id},
            ).fetchone()
            if owned is None:
                return False
            session.execute(
                text(
                    "INSERT INTO outfit_wears (outfit_id, user_id, worn_date) "
                    "VALUES (:outfit_id, :user_id, CURRENT_DATE) "
                    "ON CONFLICT (outfit_id, worn_date) DO NOTHING"
                ),
                {"outfit_id": outfit_id, "user_id": user_id},
            )
            for item_id in owned_item_ids:
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
