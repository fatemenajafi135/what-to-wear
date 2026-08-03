"""Proves `sessions`' and `messages`' RLS policies AND table-level GRANTs
actually isolate rows — independent of this backend's own database
connection (same technique as `test_outfits_rls.py`, mirrored for feature
011's two new tables).

The pooler role this app connects as (`postgres`) has BYPASSRLS
(specs/004-closet-read/research.md §1), so testing through the app's own
session/repository would give a false pass — the query-level
`WHERE user_id = ...` filter alone would make the test succeed even if the
RLS policy or the GRANT were missing or wrong. This connects directly to
Postgres on the direct port (54322) as the `authenticated` role instead —
if the table-level GRANT (migration 0011) were missing, every statement
below would fail with "permission denied for table sessions/messages"
before RLS is ever evaluated, so a passing test proves both the policy and
the GRANT, not just one of them (design-decisions.md §44/§45; CLAUDE.md
notes this exact gap has bitten the project before).

Requires a running local Supabase stack (`cd infra && npx supabase start`).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import psycopg
import pytest

_DIRECT_DSN = "postgresql://authenticator:postgres@127.0.0.1:54322/postgres"
_ADMIN_DSN = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"

USER_A = str(uuid.uuid4())
USER_B = str(uuid.uuid4())


def _connect_as(user_id: str | None) -> psycopg.Connection:
    conn = psycopg.connect(_DIRECT_DSN)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET ROLE authenticated")
        if user_id is not None:
            cur.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (user_id,))
    return conn


@pytest.fixture
def seeded_rows() -> Iterator[dict[str, str]]:
    admin = psycopg.connect(_ADMIN_DSN)
    admin.autocommit = True
    ids: dict[str, str] = {}
    with admin.cursor() as cur:
        for key, user_id in [("a", USER_A), ("b", USER_B)]:
            thread_id = str(uuid.uuid4())
            cur.execute("INSERT INTO sessions (id, user_id) VALUES (%s, %s)", (thread_id, user_id))
            cur.execute(
                "INSERT INTO messages (session_id, user_id, kind, text) VALUES (%s, %s, 'user_message', %s)",
                (thread_id, user_id, f"Message from {key}"),
            )
            ids[key] = thread_id
    yield ids
    with admin.cursor() as cur:
        cur.execute("DELETE FROM messages WHERE user_id IN (%s, %s)", (USER_A, USER_B))
        cur.execute("DELETE FROM sessions WHERE user_id IN (%s, %s)", (USER_A, USER_B))
    admin.close()


class TestSessionsRLS:
    def test_user_sees_only_their_own_sessions(self, seeded_rows: dict[str, str]) -> None:
        conn_a = _connect_as(USER_A)
        try:
            with conn_a.cursor() as cur:
                cur.execute("SELECT id, user_id FROM sessions")
                rows = cur.fetchall()
        finally:
            conn_a.close()

        assert [(str(row_id), str(user_id)) for row_id, user_id in rows] == [(seeded_rows["a"], USER_A)]

    def test_second_user_sees_only_their_own_sessions(self, seeded_rows: dict[str, str]) -> None:
        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur:
                cur.execute("SELECT id, user_id FROM sessions")
                rows = cur.fetchall()
        finally:
            conn_b.close()

        assert [(str(row_id), str(user_id)) for row_id, user_id in rows] == [(seeded_rows["b"], USER_B)]

    def test_no_claim_set_sees_nothing(self, seeded_rows: dict[str, str]) -> None:
        conn = _connect_as(None)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM sessions")
                rows = cur.fetchall()
        finally:
            conn.close()

        assert rows == []

    def test_user_cannot_insert_a_session_claiming_another_users_id(self, seeded_rows: dict[str, str]) -> None:
        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur, pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    "INSERT INTO sessions (id, user_id) VALUES (%s, %s)",
                    (str(uuid.uuid4()), USER_A),
                )
        finally:
            conn_b.close()

    def test_user_cannot_delete_another_users_session(self, seeded_rows: dict[str, str]) -> None:
        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE id = %s", (seeded_rows["a"],))
                assert cur.rowcount == 0
        finally:
            conn_b.close()

        conn_a = _connect_as(USER_A)
        try:
            with conn_a.cursor() as cur:
                cur.execute("SELECT id FROM sessions WHERE id = %s", (seeded_rows["a"],))
                assert cur.fetchone() is not None
        finally:
            conn_a.close()


class TestMessagesRLS:
    def test_user_sees_only_their_own_messages(self, seeded_rows: dict[str, str]) -> None:
        conn_a = _connect_as(USER_A)
        try:
            with conn_a.cursor() as cur:
                cur.execute("SELECT session_id, text FROM messages")
                rows = cur.fetchall()
        finally:
            conn_a.close()

        assert [(str(session_id), text) for session_id, text in rows] == [(seeded_rows["a"], "Message from a")]

    def test_second_user_sees_only_their_own_messages(self, seeded_rows: dict[str, str]) -> None:
        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur:
                cur.execute("SELECT session_id, text FROM messages")
                rows = cur.fetchall()
        finally:
            conn_b.close()

        assert [(str(session_id), text) for session_id, text in rows] == [(seeded_rows["b"], "Message from b")]

    def test_no_claim_set_sees_nothing(self, seeded_rows: dict[str, str]) -> None:
        conn = _connect_as(None)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM messages")
                rows = cur.fetchall()
        finally:
            conn.close()

        assert rows == []

    def test_user_cannot_insert_a_message_claiming_another_users_id(self, seeded_rows: dict[str, str]) -> None:
        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur, pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    "INSERT INTO messages (session_id, user_id, kind, text) VALUES (%s, %s, 'user_message', 'forged')",
                    (seeded_rows["b"], USER_A),
                )
        finally:
            conn_b.close()

    def test_user_cannot_delete_another_users_message(self, seeded_rows: dict[str, str]) -> None:
        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur:
                cur.execute("DELETE FROM messages WHERE session_id = %s", (seeded_rows["a"],))
                assert cur.rowcount == 0
        finally:
            conn_b.close()

        conn_a = _connect_as(USER_A)
        try:
            with conn_a.cursor() as cur:
                cur.execute("SELECT id FROM messages WHERE session_id = %s", (seeded_rows["a"],))
                assert cur.fetchone() is not None
        finally:
            conn_a.close()
