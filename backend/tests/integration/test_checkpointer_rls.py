"""Proves LangGraph's checkpointer tables are not reachable by an ordinary
signed-in user.

These tables are created by `PostgresSaver.setup()`, not by a migration, so
they never passed through 0002's RLS-and-GRANT convention and Postgres'
default ACL for `public` gave `authenticated` full CRUD on them. Because
PostgREST serves the whole `public` schema, that made every user's
checkpointed graph state readable AND writable by any other signed-in user
over `/rest/v1/checkpoints` — and those rows carry the serialized `Context`:
wardrobe item names, colors, photo_paths, the owner's `user_id`, and their
free-text occasion.

The exposure was confirmed by exploiting it (a brand-new account with an
empty closet read other users' rows), which is why this test asserts at the
PostgREST layer rather than only checking `pg_class.relrowsecurity` — the
REST path is where the data actually escaped, and a grant/policy assertion
alone would not have caught it.

`memory/store._harden_checkpointer_tables` is what closes it, on every
`get_checkpointer()` that builds a real `PostgresSaver`.

Requires a running local Supabase stack AND a checkpointer that has been
initialized at least once (the tables do not exist before that).
"""

from __future__ import annotations

import uuid

import psycopg
import pytest
import requests

_DIRECT_DSN = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
_API = "http://127.0.0.1:54321"
_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9."
    "CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0"
)


def _checkpointer_tables() -> list[str]:
    with psycopg.connect(_DIRECT_DSN) as conn, conn.cursor() as cur:
        cur.execute("select tablename from pg_tables where schemaname = 'public' and tablename like 'checkpoint%'")
        return [row[0] for row in cur.fetchall()]


@pytest.fixture(scope="module")
def tables() -> list[str]:
    """Initializes the checkpointer first rather than skipping when the
    tables are absent. On a database freshly reset from empty — CI's state,
    and the state a real deploy starts in — nothing has run `setup()` yet,
    so a skip here would mean this test silently protects nothing in the one
    environment where the regression matters most."""
    from whattowear.memory.store import get_checkpointer

    checkpointer = get_checkpointer()
    if type(checkpointer).__name__ != "PostgresSaver":
        pytest.skip("no checkpointer-capable database configured; nothing to harden")

    found = _checkpointer_tables()
    assert found, "PostgresSaver ran but created no checkpoint* tables"
    return found


@pytest.fixture(scope="module")
def user_token() -> str:
    """A brand-new signed-up user — the exact shape of the attacker in the
    original exploit: authenticated, but owning nothing."""
    email = f"checkpointer-rls-{uuid.uuid4().hex[:8]}@example.com"
    response = requests.post(
        f"{_API}/auth/v1/signup",
        headers={"apikey": _ANON_KEY},
        json={"email": email, "password": "Test-Passw0rd!"},
        timeout=15,
    )
    token = response.json().get("access_token")
    if not token:
        pytest.skip(f"could not sign up a probe user: {response.status_code}")
    return str(token)


class TestCheckpointerTablesAreNotPubliclyReadable:
    def test_rls_is_enabled_on_every_checkpointer_table(self, tables: list[str]) -> None:
        with psycopg.connect(_DIRECT_DSN) as conn, conn.cursor() as cur:
            for table in tables:
                cur.execute(
                    "select relrowsecurity from pg_class where relname = %s and relnamespace = 'public'::regnamespace",
                    (table,),
                )
                row = cur.fetchone()
                assert row is not None, f"{table} not found"
                assert row[0] is True, f"RLS is OFF on {table}"

    def test_authenticated_and_anon_hold_no_privileges(self, tables: list[str]) -> None:
        with psycopg.connect(_DIRECT_DSN) as conn, conn.cursor() as cur:
            for table in tables:
                cur.execute(
                    "select grantee, privilege_type from information_schema.role_table_grants "
                    "where table_schema = 'public' and table_name = %s and grantee in ('authenticated', 'anon')",
                    (table,),
                )
                assert cur.fetchall() == [], f"{table} still grants privileges to authenticated/anon"

    def test_a_signed_in_user_cannot_read_checkpoints_over_postgrest(self, tables: list[str], user_token: str) -> None:
        """The original exploit, verbatim: this returned other users' rows."""
        for table in tables:
            response = requests.get(
                f"{_API}/rest/v1/{table}",
                params={"select": "*", "limit": "5"},
                headers={"apikey": _ANON_KEY, "Authorization": f"Bearer {user_token}"},
                timeout=15,
            )
            leaked = response.status_code == 200 and response.json()
            assert not leaked, f"{table} leaked {len(response.json())} row(s) to an unrelated user"
