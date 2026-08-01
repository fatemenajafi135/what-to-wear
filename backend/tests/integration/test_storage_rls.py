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

import jwt
import psycopg
import pytest
import requests

# Direct Postgres connection (not the transaction-mode pooler) — SET ROLE
# needs to persist for the query that follows it, matching
# test_wardrobe_rls.py's own reasoning exactly.
_DIRECT_DSN = "postgresql://authenticator:postgres@127.0.0.1:54322/postgres"
_STORAGE_URL = "http://127.0.0.1:54321/storage/v1"

# Supabase CLI's fixed, publicly-documented local-dev demo JWT secret —
# identical on every `supabase start` that doesn't override
# [auth.jwt_secret] in config.toml (this project doesn't), not a
# per-project or production credential. Used only to mint a service_role
# token for test cleanup below, against 127.0.0.1.
_LOCAL_DEMO_JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"


def _service_role_token() -> str:
    """Admin-level token for teardown ONLY. `storage.objects` has a
    `protect_delete()` trigger that rejects a direct SQL `DELETE` for
    every role, including the bypass-privileged one this file's fixture
    otherwise uses to seed rows — confirmed against the live stack.
    Cleanup has to go through the Storage HTTP API instead."""
    return jwt.encode({"role": "service_role", "iss": "supabase-demo"}, _LOCAL_DEMO_JWT_SECRET, algorithm="HS256")


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
    conn.close()

    yield object_name

    requests.delete(
        f"{_STORAGE_URL}/object/{BUCKET}/{object_name}",
        headers={"Authorization": f"Bearer {_service_role_token()}"},
        timeout=10,
    )


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

    # No test_other_user_cannot_delete_object here — deliberately, not an
    # oversight. `storage.objects`' `protect_delete()` trigger rejects a
    # direct SQL `DELETE` unconditionally, for every role, including the
    # `postgres`-equivalent bypass-privileged connection this file's own
    # fixture uses to seed rows (confirmed live: `psycopg.errors.
    # InsufficientPrivilege` fires before RLS is ever reached). A version
    # of this test previously existed and appeared to pass — `rowcount ==
    # 0` — but for the wrong reason: the trigger, not the policy, blocked
    # it, so it proved nothing about RLS and would have "passed" identically
    # against a broken or missing policy. The `wardrobe_photos_owner_rw`
    # policy is `for all`, one `using` clause gating SELECT/UPDATE/DELETE
    # alike — the exact clause DELETE would be checked against is already
    # exercised, at the SQL level, by `test_other_user_cannot_read_object`
    # (SELECT) and `test_other_user_cannot_overwrite_object` (UPDATE).
    # Proving DELETE specifically would require a real signed-up Supabase
    # Auth user (there's no SQL-role-simulation path around the trigger),
    # which is meaningfully more integration-test machinery — sign-up,
    # session exchange, user cleanup — for a claim the `using` clause
    # already covers. Not worth it now; revisit if this policy ever stops
    # being a single unified `for all` grant.
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
