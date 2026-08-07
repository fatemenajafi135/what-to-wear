"""Proves `wardrobe_items`' and `catalog_items`' RLS policies actually
isolate rows — independent of this backend's own database connection.

specs/004-closet-read/research.md §1: the pooler role this app connects as
(`postgres`, via the local `pooler-dev` Supavisor tenant) has BYPASSRLS, so
Postgres skips policy evaluation entirely for every query this app issues —
testing through the app's own session/repository would give a false pass,
since the query-level `WHERE user_id = ...` filter alone would make the
test succeed even if the RLS policy were missing or wrong.

This test instead connects directly to Postgres on the **direct** port
(54322, not the 54329 pooler) as the `authenticator` role — the one role in
the local stack that can log in, does NOT bypass RLS, and is a member of
`authenticated`/`anon`/`service_role` (confirmed via `pg_auth_members`;
research.md §2). It's the same mechanism PostgREST itself uses per request:
`SET ROLE authenticated`, then `set_config('request.jwt.claim.sub', ...)`.
Every assertion here runs a raw, UNFILTERED `SELECT * FROM wardrobe_items`
— no `WHERE user_id = ...` anywhere in this file — so a passing test proves
the policy itself, not the application layer.

Requires a running local Supabase stack (`cd infra && npx supabase start`).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import psycopg
import pytest

# Direct Postgres connection (not the transaction-mode pooler) — SET ROLE
# needs to persist for the query that follows it, which the pooler's
# per-statement/transaction semantics don't reliably guarantee for a
# dedicated test connection like this one.
_DIRECT_DSN = "postgresql://authenticator:postgres@127.0.0.1:54322/postgres"

USER_A = str(uuid.uuid4())
USER_B = str(uuid.uuid4())


def _connect_as(user_id: str | None) -> psycopg.Connection:
    conn = psycopg.connect(_DIRECT_DSN)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET ROLE authenticated")
        if user_id is not None:
            # `false` (session-scoped), not `true` (transaction-local): this
            # connection runs with autocommit=True, so each statement is its
            # own implicit transaction — a `true`/local setting would reset
            # the instant this statement's own implicit transaction ends,
            # before the SELECT that's supposed to read it ever runs.
            cur.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (user_id,))
    return conn


@pytest.fixture
def seeded_rows() -> Iterator[None]:
    # Seeded via a bypass-privileged connection (the same role this app's
    # pooler uses) — matches how rows actually get created today (feature
    # 005's write path doesn't exist yet).
    admin = psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres")
    admin.autocommit = True
    with admin.cursor() as cur:
        for user_id, category in [(USER_A, "t-shirt"), (USER_B, "jeans")]:
            cur.execute(
                "INSERT INTO wardrobe_items (user_id, category, colors, formality, warmth, season, source)"
                " VALUES (%s, %s, '{}', 'casual', 1, '{}', 'upload')",
                (user_id, category),
            )
    yield
    with admin.cursor() as cur:
        cur.execute("DELETE FROM wardrobe_items WHERE user_id IN (%s, %s)", (USER_A, USER_B))
    admin.close()


class TestWardrobeItemsRLS:
    def test_user_sees_only_their_own_rows(self, seeded_rows: None) -> None:
        conn_a = _connect_as(USER_A)
        try:
            with conn_a.cursor() as cur:
                cur.execute("SELECT user_id, category FROM wardrobe_items")
                rows = cur.fetchall()
        finally:
            conn_a.close()

        assert [(str(user_id), category) for user_id, category in rows] == [(USER_A, "t-shirt")]

    def test_second_user_sees_only_their_own_rows(self, seeded_rows: None) -> None:
        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur:
                cur.execute("SELECT user_id, category FROM wardrobe_items")
                rows = cur.fetchall()
        finally:
            conn_b.close()

        assert [(str(user_id), category) for user_id, category in rows] == [(USER_B, "jeans")]

    def test_no_claim_set_sees_nothing(self, seeded_rows: None) -> None:
        """`auth.uid()` resolves to NULL with no claim set; the policy
        `auth.uid() = user_id` is never true against NULL, so an
        unauthenticated-shaped connection sees zero rows — not everyone's."""
        conn = _connect_as(None)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM wardrobe_items")
                rows = cur.fetchall()
        finally:
            conn.close()

        assert rows == []

    def test_user_cannot_update_another_users_row(self, seeded_rows: None) -> None:
        """Feature 005 (§9 DoD "RLS proven"): an unfiltered UPDATE as user B
        against user A's row must affect zero rows — the policy, not just
        the application's own `WHERE user_id = ...`, is what blocks it."""
        admin = psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres")
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute("SELECT id FROM wardrobe_items WHERE user_id = %s", (USER_A,))
            (item_a_id,) = cur.fetchone()
        admin.close()

        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur:
                cur.execute("UPDATE wardrobe_items SET name = 'hijacked' WHERE id = %s", (item_a_id,))
                assert cur.rowcount == 0
        finally:
            conn_b.close()

        admin = psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres")
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute("SELECT name FROM wardrobe_items WHERE id = %s", (item_a_id,))
            (name,) = cur.fetchone()
        admin.close()
        assert name != "hijacked"

    def test_user_cannot_delete_another_users_row(self, seeded_rows: None) -> None:
        """Same proof for DELETE — the other half of feature 005's write
        surface."""
        admin = psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres")
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute("SELECT id FROM wardrobe_items WHERE user_id = %s", (USER_A,))
            (item_a_id,) = cur.fetchone()
        admin.close()

        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur:
                cur.execute("DELETE FROM wardrobe_items WHERE id = %s", (item_a_id,))
                assert cur.rowcount == 0
        finally:
            conn_b.close()

        conn_a = _connect_as(USER_A)
        try:
            with conn_a.cursor() as cur:
                cur.execute("SELECT id FROM wardrobe_items WHERE id = %s", (item_a_id,))
                assert cur.fetchone() is not None
        finally:
            conn_a.close()


class TestItemWearsRLS:
    """Feature 005: same `authenticator`-role direct-connection technique as
    `TestWardrobeItemsRLS` — proves the policy itself, independent of this
    backend's own BYPASSRLS pooler connection."""

    @pytest.fixture
    def item_ids(self) -> Iterator[dict[str, str]]:
        admin = psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres")
        admin.autocommit = True
        ids: dict[str, str] = {}
        with admin.cursor() as cur:
            for key, user_id, category in [("a", USER_A, "t-shirt"), ("b", USER_B, "jeans")]:
                cur.execute(
                    "INSERT INTO wardrobe_items (user_id, category, colors, formality, warmth, season, source)"
                    " VALUES (%s, %s, '{}', 'casual', 1, '{}', 'upload') RETURNING id",
                    (user_id, category),
                )
                (item_id,) = cur.fetchone()
                ids[key] = str(item_id)
        yield ids
        with admin.cursor() as cur:
            cur.execute("DELETE FROM wardrobe_items WHERE id = ANY(%s)", (list(ids.values()),))
        admin.close()

    def test_user_sees_only_their_own_wear_rows(self, item_ids: dict[str, str]) -> None:
        admin = psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres")
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute(
                "INSERT INTO item_wears (item_id, user_id) VALUES (%s, %s), (%s, %s)",
                (item_ids["a"], USER_A, item_ids["b"], USER_B),
            )
        admin.close()

        conn_a = _connect_as(USER_A)
        try:
            with conn_a.cursor() as cur:
                cur.execute("SELECT item_id FROM item_wears")
                rows = cur.fetchall()
        finally:
            conn_a.close()

        assert [str(row[0]) for row in rows] == [item_ids["a"]]

    def test_user_cannot_insert_a_wear_row_against_another_users_item(self, item_ids: dict[str, str]) -> None:
        """RLS's `with check (auth.uid() = user_id)` alone only proves a
        wear row's own `user_id` is the caller's — it can't see whether
        `item_id` belongs to that same user. A forged insert claiming
        `user_id = USER_B` (satisfying RLS) but pointing `item_id` at
        user A's item is instead blocked by the migration's composite
        foreign key (`item_id, user_id) references wardrobe_items (id,
        user_id)`), which is exactly why that constraint exists rather
        than a plain `item_id references wardrobe_items(id)`."""
        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur, pytest.raises(psycopg.errors.ForeignKeyViolation):
                cur.execute(
                    "INSERT INTO item_wears (item_id, user_id) VALUES (%s, %s)",
                    (item_ids["a"], USER_B),
                )
        finally:
            conn_b.close()


class TestCatalogItemsRLS:
    def test_shared_catalog_readable_by_any_authenticated_user(self) -> None:
        admin = psycopg.connect("postgresql://postgres:postgres@127.0.0.1:54322/postgres")
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute(
                "INSERT INTO catalog_items (category, colors, formality, warmth, season) VALUES"
                " ('jacket', '{}', 'casual', 2, '{}') RETURNING id"
            )
            (catalog_id,) = cur.fetchone()

        try:
            for user_id in (USER_A, USER_B):
                conn = _connect_as(user_id)
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT id FROM catalog_items WHERE id = %s", (catalog_id,))
                        assert cur.fetchone() == (catalog_id,)
                finally:
                    conn.close()
        finally:
            with admin.cursor() as cur:
                cur.execute("DELETE FROM catalog_items WHERE id = %s", (catalog_id,))
            admin.close()
