"""Proves `outfits`' RLS policy AND table-level GRANT actually isolate rows
— independent of this backend's own database connection (same technique as
`test_wardrobe_rls.py`, mirrored for feature 009's new table).

The pooler role this app connects as (`postgres`) has BYPASSRLS
(specs/004-closet-read/research.md §1), so testing through the app's own
session/repository would give a false pass — the query-level
`WHERE user_id = ...` filter alone would make the test succeed even if the
RLS policy or the GRANT were missing or wrong. This connects directly to
Postgres on the direct port (54322) as the `authenticated` role instead —
if the table-level GRANT (migration 0009) were missing, every statement
below would fail with "permission denied for table outfits" before RLS is
ever evaluated, so a passing test proves both the policy and the GRANT, not
just one of them (design-decisions.md §32; CLAUDE.md notes this exact gap
has bitten the project twice before).

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
        for key, user_id, occasion in [("a", USER_A, "Rainy commute"), ("b", USER_B, "Dinner date")]:
            cur.execute(
                "INSERT INTO outfits (user_id, occasion, meta_line, rationale_text, match_label, item_ids)"
                " VALUES (%s, %s, 'meta', 'rationale', 'great', '{}') RETURNING id",
                (user_id, occasion),
            )
            (outfit_id,) = cur.fetchone()
            ids[key] = str(outfit_id)
    yield ids
    with admin.cursor() as cur:
        cur.execute("DELETE FROM outfits WHERE user_id IN (%s, %s)", (USER_A, USER_B))
    admin.close()


class TestOutfitsRLS:
    def test_user_sees_only_their_own_rows(self, seeded_rows: dict[str, str]) -> None:
        conn_a = _connect_as(USER_A)
        try:
            with conn_a.cursor() as cur:
                cur.execute("SELECT user_id, occasion FROM outfits")
                rows = cur.fetchall()
        finally:
            conn_a.close()

        assert [(str(user_id), occasion) for user_id, occasion in rows] == [(USER_A, "Rainy commute")]

    def test_second_user_sees_only_their_own_rows(self, seeded_rows: dict[str, str]) -> None:
        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur:
                cur.execute("SELECT user_id, occasion FROM outfits")
                rows = cur.fetchall()
        finally:
            conn_b.close()

        assert [(str(user_id), occasion) for user_id, occasion in rows] == [(USER_B, "Dinner date")]

    def test_no_claim_set_sees_nothing(self, seeded_rows: dict[str, str]) -> None:
        conn = _connect_as(None)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM outfits")
                rows = cur.fetchall()
        finally:
            conn.close()

        assert rows == []

    def test_user_cannot_toggle_favorite_on_another_users_row(self, seeded_rows: dict[str, str]) -> None:
        """The app-level proof of the same thing lives in
        test_recommend_routes.py::TestToggleOutfitFavorite (via the real
        route/repository); this is the policy-level proof independent of
        this backend's own BYPASSRLS connection."""
        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur:
                cur.execute(
                    "UPDATE outfits SET favorite = NOT favorite WHERE id = %s",
                    (seeded_rows["a"],),
                )
                assert cur.rowcount == 0
        finally:
            conn_b.close()

        admin = psycopg.connect(_ADMIN_DSN)
        admin.autocommit = True
        with admin.cursor() as cur:
            cur.execute("SELECT favorite FROM outfits WHERE id = %s", (seeded_rows["a"],))
            (favorite,) = cur.fetchone()
        admin.close()
        assert favorite is True  # unchanged — still the `create()` default

    def test_user_cannot_delete_another_users_row(self, seeded_rows: dict[str, str]) -> None:
        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur:
                cur.execute("DELETE FROM outfits WHERE id = %s", (seeded_rows["a"],))
                assert cur.rowcount == 0
        finally:
            conn_b.close()

        conn_a = _connect_as(USER_A)
        try:
            with conn_a.cursor() as cur:
                cur.execute("SELECT id FROM outfits WHERE id = %s", (seeded_rows["a"],))
                assert cur.fetchone() is not None
        finally:
            conn_a.close()

    def test_user_cannot_insert_a_row_claiming_another_users_id(self, seeded_rows: dict[str, str]) -> None:
        """RLS's `with check (auth.uid() = user_id)` blocks an insert where
        the claimed `user_id` doesn't match the caller's own JWT claim —
        the second half of the GRANT+RLS proof (insert, not just read)."""
        conn_b = _connect_as(USER_B)
        try:
            with conn_b.cursor() as cur, pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    "INSERT INTO outfits (user_id, occasion, meta_line, rationale_text, match_label, item_ids)"
                    " VALUES (%s, 'forged', 'meta', 'rationale', 'great', '{}')",
                    (USER_A,),
                )
        finally:
            conn_b.close()
