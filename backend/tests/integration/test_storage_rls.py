"""Proves the `wardrobe-photos` bucket's `storage.objects` RLS policy
actually isolates objects — independent of this backend's own database
connection, same methodology as `test_wardrobe_rls.py`.

Unlike `wardrobe_items`, this policy is the REAL enforcement for this
feature's own traffic, not just documented convention: every upload and
signed-URL request goes through Supabase Storage's own HTTP API
(`adapters/storage.py`), authenticated with the caller's JWT, which
evaluates this exact policy on every call — this backend's pooler
connection never touches `storage.objects` directly at all
(specs/006-photo-upload-vision/research.md §2). Testing at the raw-SQL/role
level here still proves the policy itself, the same way
`test_wardrobe_rls.py` does for `wardrobe_items` — and additionally, this
IS the actual code path Storage's HTTP layer relies on, not merely a proxy
for it.

Requires a running local Supabase stack (`cd infra && npx supabase start`).
Cannot run in this sandbox (research.md §13) — written to the same standard
`test_wardrobe_rls.py` already meets.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import psycopg
import pytest

# Direct Postgres connection (not the transaction-mode pooler) — SET ROLE
# needs to persist for the query that follows it, matching
# test_wardrobe_rls.py's own reasoning exactly.
_DIRECT_DSN = "postgresql://authenticator:postgres@127.0.0.1:54322/postgres"

USER_A = str(uuid.uuid4())
USER_B = str(uuid.uuid4())
BUCKET = "wardrobe-photos"


def _connect_as(user_id: str | None) -> psycopg.Connection:
    conn = psycopg.connect(_DIRECT_DSN)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET ROLE authenticated")
        if user_id is not None:
            cur.execute("SELECT set_config('request.jwt.claim.sub', %s, false)", (user_id,))
    return conn


@pytest.fixture
def user_a_object() -> Iterator[str]:
    # Seeded via a bypass-privileged connection (mirrors how a real upload
    # via adapters.storage.upload_photo lands a row — the app's own pooler
    # role has BYPASSRLS, same as for wardrobe_items).
    object_name = f"{USER_A}/{uuid.uuid4()}-shirt.jpg"
    conn = psycopg.connect(_DIRECT_DSN.replace("authenticator", "postgres"))
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO storage.objects (bucket_id, name) VALUES (%s, %s)",
            (BUCKET, object_name),
        )
    yield object_name
    with conn.cursor() as cur:
        cur.execute("DELETE FROM storage.objects WHERE bucket_id = %s AND name = %s", (BUCKET, object_name))
    conn.close()


class TestWardrobePhotosRLS:
    def test_owner_can_read_own_object(self, user_a_object: str) -> None:
        conn = _connect_as(USER_A)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM storage.objects WHERE bucket_id = %s AND name = %s", (BUCKET, user_a_object))
            assert cur.fetchone() is not None
        conn.close()

    def test_other_user_cannot_read_object(self, user_a_object: str) -> None:
        conn = _connect_as(USER_B)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM storage.objects WHERE bucket_id = %s AND name = %s", (BUCKET, user_a_object))
            assert cur.fetchone() is None  # policy filters the row out entirely, not a 403
        conn.close()

    def test_other_user_cannot_overwrite_object(self, user_a_object: str) -> None:
        conn = _connect_as(USER_B)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE storage.objects SET metadata = '{\"tampered\": true}'::jsonb "
                "WHERE bucket_id = %s AND name = %s",
                (BUCKET, user_a_object),
            )
            assert cur.rowcount == 0  # RLS blocks the row match, not just a permission error
        conn.close()

    def test_other_user_cannot_delete_object(self, user_a_object: str) -> None:
        conn = _connect_as(USER_B)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM storage.objects WHERE bucket_id = %s AND name = %s", (BUCKET, user_a_object))
            assert cur.rowcount == 0
        conn.close()

    def test_other_user_cannot_upload_under_someone_elses_prefix(self) -> None:
        # Mirrors what `adapters.storage.upload_photo` would attempt if a
        # caller tried to write under a foreign user_id prefix — the
        # `with check` clause must reject the INSERT itself, not just
        # later reads.
        conn = _connect_as(USER_B)
        object_name = f"{USER_A}/{uuid.uuid4()}-forged.jpg"
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("INSERT INTO storage.objects (bucket_id, name) VALUES (%s, %s)", (BUCKET, object_name))
        conn.close()
