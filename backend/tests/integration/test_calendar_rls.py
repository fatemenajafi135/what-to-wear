"""Proves `calendar_connections`' and `picked_events`' RLS policies actually
isolate rows — independent of this backend's own database connection.
Mirrors tests/integration/test_wardrobe_rls.py (feature 004) exactly; see
that file's docstring and specs/004-closet-read/research.md §1-2 for the
full reasoning this one doesn't repeat: this backend's own pooler connection
has BYPASSRLS, so testing through the app's own session/repository would
give a false pass.

Connects directly to Postgres on the direct port (54322, not a pooler) as
the `authenticator` role, `SET ROLE authenticated`, sets
`request.jwt.claim.sub`, and runs a raw, UNFILTERED `SELECT * FROM
calendar_connections` / `picked_events` — no `WHERE user_id = ...`
anywhere in this file — so a passing test proves the policy itself.

Requires a running local Postgres with migration `0004` applied
(`cd infra && npx supabase start` normally; this session's own bare-Postgres
harness in its place — see specs/012-calendar/research.md §8).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import psycopg
import pytest

_DIRECT_DSN = "postgresql://authenticator:postgres@127.0.0.1:54322/postgres"

USER_A = str(uuid.uuid4())
USER_B = str(uuid.uuid4())


def _connect_as(user_id: str | None) -> psycopg.Connection:
    conn = psycopg.connect(_DIRECT_DSN)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET ROLE authenticated")
        if user_id is not None:
            # `false` (session-scoped), not `true` (transaction-local) —
            # this connection runs with autocommit=True, so a `true`
            # setting would reset before the following SELECT ever runs.
            cur.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (user_id,))
    return conn


@pytest.fixture
def seeded_connections() -> Iterator[None]:
    admin = psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres")
    admin.autocommit = True
    with admin.cursor() as cur:
        for user_id in (USER_A, USER_B):
            cur.execute(
                "INSERT INTO calendar_connections"
                " (user_id, access_token_encrypted, refresh_token_encrypted, token_expires_at)"
                " VALUES (%s, 'ct-access', 'ct-refresh', now() + interval '1 hour')",
                (user_id,),
            )
    yield
    with admin.cursor() as cur:
        cur.execute("DELETE FROM calendar_connections WHERE user_id IN (%s, %s)", (USER_A, USER_B))
    admin.close()


@pytest.fixture
def seeded_picked_events() -> Iterator[None]:
    admin = psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres")
    admin.autocommit = True
    with admin.cursor() as cur:
        for user_id, title in [(USER_A, "A's dinner"), (USER_B, "B's meeting")]:
            cur.execute(
                "INSERT INTO picked_events (user_id, google_event_id, title, start_time) VALUES (%s, 'evt', %s, now())",
                (user_id, title),
            )
    yield
    with admin.cursor() as cur:
        cur.execute("DELETE FROM picked_events WHERE user_id IN (%s, %s)", (USER_A, USER_B))
    admin.close()


class TestCalendarConnectionsRLS:
    def test_user_sees_only_their_own_row(self, seeded_connections: None) -> None:
        conn = _connect_as(USER_A)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM calendar_connections")
                rows = cur.fetchall()
        finally:
            conn.close()
        assert [str(user_id) for (user_id,) in rows] == [USER_A]

    def test_second_user_sees_only_their_own_row(self, seeded_connections: None) -> None:
        conn = _connect_as(USER_B)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM calendar_connections")
                rows = cur.fetchall()
        finally:
            conn.close()
        assert [str(user_id) for (user_id,) in rows] == [USER_B]

    def test_no_claim_set_sees_nothing(self, seeded_connections: None) -> None:
        conn = _connect_as(None)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM calendar_connections")
                rows = cur.fetchall()
        finally:
            conn.close()
        assert rows == []


class TestPickedEventsRLS:
    def test_user_sees_only_their_own_row(self, seeded_picked_events: None) -> None:
        conn = _connect_as(USER_A)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id, title FROM picked_events")
                rows = cur.fetchall()
        finally:
            conn.close()
        assert [(str(user_id), title) for user_id, title in rows] == [(USER_A, "A's dinner")]

    def test_second_user_sees_only_their_own_row(self, seeded_picked_events: None) -> None:
        conn = _connect_as(USER_B)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id, title FROM picked_events")
                rows = cur.fetchall()
        finally:
            conn.close()
        assert [(str(user_id), title) for user_id, title in rows] == [(USER_B, "B's meeting")]

    def test_no_claim_set_sees_nothing(self, seeded_picked_events: None) -> None:
        conn = _connect_as(None)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM picked_events")
                rows = cur.fetchall()
        finally:
            conn.close()
        assert rows == []
