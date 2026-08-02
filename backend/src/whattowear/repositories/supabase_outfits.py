"""Database-backed persistence for saved outfits (feature 009,
specs/009-suggestion-pager/data-model.md).

The project's first outfit persistence — before this, a suggestion existed
only inside one HTTP response. Mirrors `supabase_closet.py`'s session/JWT-
claim pattern exactly: `request.jwt.claim.sub` is set per transaction for
the same forward-compatibility reason (the pooler role has BYPASSRLS today,
so the query-level `WHERE user_id = ...` is the real isolation guarantee for
this backend's own traffic; the outfits table's own RLS + GRANT is defense-
in-depth for any other access path — see infra/supabase/migrations/
0009_outfits.sql).

No `list`/`get` method here — nothing in this feature reads outfits back;
that's feature 010's job.
"""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.db import get_session

_session_scope = contextmanager(get_session)


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
    ) -> str:
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text(
                    "INSERT INTO outfits (user_id, occasion, meta_line, rationale_text, match_label, item_ids) "
                    "VALUES (:user_id, :occasion, :meta_line, :rationale_text, :match_label, :item_ids) "
                    "RETURNING id"
                ),
                {
                    "user_id": user_id,
                    "occasion": occasion,
                    "meta_line": meta_line,
                    "rationale_text": rationale_text,
                    "match_label": match_label,
                    "item_ids": item_ids,
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
