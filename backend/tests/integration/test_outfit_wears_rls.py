"""Proves `outfit_wears`' RLS policy AND table-level GRANT actually isolate
rows — same `authenticator`-role direct-connection technique as
`test_outfits_rls.py` and `test_wardrobe_rls.py::TestItemWearsRLS` (mirrored
here for feature 010's new table, design-decisions.md §39).

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
def outfit_ids() -> Iterator[dict[str, str]]:
    admin = psycopg.connect(_ADMIN_DSN)
    admin.autocommit = True
    ids: dict[str, str] = {}
    with admin.cursor() as cur:
        for key, user_id, occasion in [("a", USER_A, "Rainy commute"), ("b", USER_B, "Dinner date")]:
            cur.execute(
                "INSERT INTO outfits (user_id, occasion, meta_line, rationale_text, match_label, item_ids, title)"
                " VALUES (%s, %s, 'meta', 'rationale', 'great', '{}', %s) RETURNING id",
                (user_id, occasion, occasion),
            )
            (outfit_id,) = cur.fetchone()
            ids[key] = str(outfit_id)
    yield ids
    with admin.cursor() as cur:
        cur.execute("DELETE FROM outfits WHERE user_id IN (%s, %s)", (USER_A, USER_B))
    admin.close()


class TestOutfitWearsRLS:
    """Same `authenticator`-role direct-connection technique as
    `TestOutfitsRLS` — proves the policy itself, independent of this
    backend's own BYPASSRLS pooler connection."""

    def test_user_sees_only_their_own_wear_rows(self, outfit_ids: dict[str, str]) -> None:
        admin = psycopg.connect(_ADMIN_DSN)
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute(
                "INSERT INTO outfit_wears (outfit_id, user_id) VALUES (%s, %s), (%s, %s)",
                (outfit_ids["a"], USER_A, outfit_ids["b"], USER_B),
            )
        admin.close()

        conn_a = _connect_as(USER_A)
        try:
            with conn_a.cursor() as cur:
                cur.execute("SELECT outfit_id FROM outfit_wears")
                rows = cur.fetchall()
        finally:
            conn_a.close()

        assert [str(row[0]) for row in rows] == [outfit_ids["a"]]

    def test_user_cannot_update_or_delete_another_users_wear_row(self, outfit_ids: dict[str, str]) -> None:
        admin = psycopg.connect(_ADMIN_DSN)
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute(
                "INSERT INTO outfit_wears (outfit_id, user_id) VALUES (%s, %s) RETURNING id",
                (outfit_ids["a"], USER_A),
            )
            (wear_id,) = cur.fetchone()
        admin.close()

        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur:
                cur.execute("DELETE FROM outfit_wears WHERE id = %s", (wear_id,))
                assert cur.rowcount == 0
        finally:
            conn_b.close()

        conn_a = _connect_as(USER_A)
        try:
            with conn_a.cursor() as cur:
                cur.execute("SELECT id FROM outfit_wears WHERE id = %s", (wear_id,))
                assert cur.fetchone() is not None
        finally:
            conn_a.close()

    def test_user_cannot_insert_a_wear_row_against_another_users_outfit(self, outfit_ids: dict[str, str]) -> None:
        """RLS's `with check (auth.uid() = user_id)` alone only proves a
        wear row's own `user_id` is the caller's — it can't see whether
        `outfit_id` belongs to that same user. A forged insert claiming
        `user_id = USER_B` (satisfying RLS) but pointing `outfit_id` at
        user A's outfit is instead blocked by the migration's composite
        foreign key (`outfit_id, user_id) references outfits (id,
        user_id)`) — same technique
        `test_wardrobe_rls.py::TestItemWearsRLS::
        test_user_cannot_insert_a_wear_row_against_another_users_item`
        already proves for `item_wears`."""
        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur, pytest.raises(psycopg.errors.ForeignKeyViolation):
                cur.execute(
                    "INSERT INTO outfit_wears (outfit_id, user_id) VALUES (%s, %s)",
                    (outfit_ids["a"], USER_B),
                )
        finally:
            conn_b.close()

    def test_no_grant_bypass_permission_denied_without_grant(self, outfit_ids: dict[str, str]) -> None:
        """Sanity check on the GRANT itself, mirroring `test_outfits_rls.py`'s
        own docstring reasoning: if `grant ... on outfit_wears to
        authenticated` were missing, this ordinary owned-row select would
        fail with "permission denied for table outfit_wears" before RLS is
        ever evaluated — a passing read here is proof the GRANT exists, not
        just the policy."""
        conn_a = _connect_as(USER_A)
        try:
            with conn_a.cursor() as cur:
                cur.execute("SELECT count(*) FROM outfit_wears")
                cur.fetchone()
        finally:
            conn_a.close()
