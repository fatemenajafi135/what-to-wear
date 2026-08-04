"""Database-backed persistence for chat history (feature 011,
specs/011-chat-history/data-model.md).

Mirrors `supabase_outfits.py`'s session/JWT-claim pattern exactly: `request.
jwt.claim.sub` is set per transaction for the same forward-compatibility
reason documented there (the pooler role has BYPASSRLS today, so the
query-level `WHERE user_id = ...` every method issues is the real isolation
guarantee for this backend's own traffic; `sessions`/`messages`' own RLS +
GRANT is defense-in-depth for any other access path — see infra/supabase/
migrations/0011_chat_history.sql).

A session's id **is** its `thread_id` (design-decisions.md §44) — there is
no second, independently generated id anywhere in this file.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from ..core.db import get_session

_session_scope = contextmanager(get_session)

MessageKind = Literal["user_message", "styling_reply", "conversational_turn", "wrap_up"]


def _set_jwt_claim(session: Session, user_id: str) -> None:
    session.execute(text("SELECT set_config('request.jwt.claim.sub', :user_id, true)"), {"user_id": user_id})


class SupabaseSessionRepository:
    def upsert_session(self, user_id: str, thread_id: str) -> None:
        """Written-on-start (design-decisions.md §44): the first call for a
        `thread_id` creates the row; every later call for the same
        `thread_id` only bumps `updated_at` — this is both "the date" a
        Chat-history row shows and the sort key for "most recently active
        first" (data-model.md).

        No ownership guard against a `thread_id` that already belongs to a
        different `user_id` — that cross-thread scenario is the same
        bounded, already-accepted risk design-decisions.md §25 documents
        for `POST /recommend/messages` generally (a guessed/reused
        `thread_id` already lets a caller invoke the pipeline against
        another user's checkpointed state); this method neither widens nor
        narrows that boundary, it just doesn't silently reassign
        `sessions.user_id` to whoever last called this."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            session.execute(
                text(
                    "INSERT INTO sessions (id, user_id) VALUES (:thread_id, :user_id) "
                    "ON CONFLICT (id) DO UPDATE SET updated_at = now()"
                ),
                {"thread_id": thread_id, "user_id": user_id},
            )
            session.commit()

    def insert_message(
        self,
        user_id: str,
        session_id: str,
        kind: MessageKind,
        text_: str = "",
        outfit_ids: list[str] | None = None,
    ) -> str:
        """`outfit_ids` defaults to `None` rather than `[]` as a mutable-
        default-argument safeguard (same convention `supabase_outfits.py::
        create` uses for `citations`/`dimension_scores`); treated as empty
        either way."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text(
                    "INSERT INTO messages (session_id, user_id, kind, text, outfit_ids) "
                    "VALUES (:session_id, :user_id, :kind, :text, :outfit_ids) "
                    "RETURNING id"
                ),
                {
                    "session_id": session_id,
                    "user_id": user_id,
                    "kind": kind,
                    "text": text_,
                    "outfit_ids": outfit_ids or [],
                },
            ).fetchone()
            session.commit()
            assert row is not None
            return str(row._mapping["id"])

    def count_user_messages(self, user_id: str, thread_id: str) -> int:
        """The turn-cap check's own source of truth (feature 016, design-decisions.md §48) — no
        separate counter, the `messages` table itself is what's counted, lifetime per thread."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text(
                    "SELECT COUNT(*) AS n FROM messages "
                    "WHERE session_id = :session_id AND user_id = :user_id AND kind = 'user_message'"
                ),
                {"session_id": thread_id, "user_id": user_id},
            ).fetchone()
            assert row is not None
            return int(row._mapping["n"])

    def list_sessions(self, user_id: str) -> list[Row[Any]]:
        """Chat history's own list — most recently active first
        (data-model.md). `preview`/`message_count`/`outfit_count` are all
        computed live, never denormalized (design-decisions.md §45's own
        reasoning for `outfit_count` applies equally to the other two —
        nothing here is expensive enough at this table's expected size to
        justify a cached counter that could drift)."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            rows = session.execute(
                text(
                    "SELECT s.id, s.updated_at, "
                    "(SELECT m.text FROM messages m WHERE m.session_id = s.id AND m.kind = 'user_message' "
                    " ORDER BY m.created_at ASC LIMIT 1) AS preview, "
                    "(SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count, "
                    "(SELECT COUNT(*) FROM outfits o WHERE o.thread_id = s.id) AS outfit_count "
                    "FROM sessions s "
                    "WHERE s.user_id = :user_id "
                    "ORDER BY s.updated_at DESC"
                ),
                {"user_id": user_id},
            ).fetchall()
            return list(rows)

    def get_session(self, user_id: str, session_id: str) -> Row[Any] | None:
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text(
                    "SELECT s.id, s.updated_at, "
                    "(SELECT COUNT(*) FROM outfits o WHERE o.thread_id = s.id) AS outfit_count "
                    "FROM sessions s "
                    "WHERE s.user_id = :user_id AND s.id = :session_id"
                ),
                {"user_id": user_id, "session_id": session_id},
            ).fetchone()
            return row

    def list_messages(self, user_id: str, session_id: str) -> list[Row[Any]]:
        """Every message for one session, in order — Session detail's own
        read pattern (data-model.md). Filters `user_id` directly on
        `messages` (denormalized column, not a join to `sessions`) so
        ownership is checked in the query itself, independent of whichever
        row `get_session` already validated — matching the handoff's own
        trap #3 (query-level ownership check, not RLS alone, since this
        backend's own connection has BYPASSRLS)."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            rows = session.execute(
                text(
                    "SELECT id, kind, text, outfit_ids, created_at FROM messages "
                    "WHERE session_id = :session_id AND user_id = :user_id "
                    "ORDER BY created_at ASC"
                ),
                {"session_id": session_id, "user_id": user_id},
            ).fetchall()
            return list(rows)
