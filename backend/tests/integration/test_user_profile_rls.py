"""Proves the `user_profile` RLS policy itself, independent of this backend's own
(superuser, RLS-bypassing) connection — see specs/013-profile-settings/research.md §1.

Opens its own `psycopg` connection per assertion, `SET LOCAL role authenticated` plus
`request.jwt.claims`, and reads through that restricted role — never through
`whattowear.core.db`'s pooled engine, which would produce a false-positive "proof" that
passes even if the policy were wrong, since the app's own role bypasses RLS entirely.
"""

from __future__ import annotations

import json
import uuid

import psycopg
from sqlalchemy import text

from whattowear.core.config import get_settings
from whattowear.core.db import get_engine


def _create_user_with_profile(style_tag: str) -> str:
    user_id = str(uuid.uuid4())
    with get_engine().begin() as conn:
        conn.execute(text("insert into auth.users (id) values (:id)"), {"id": user_id})
        conn.execute(
            text("insert into user_profile (user_id, style_tags) values (:id, :tags)"),
            {"id": user_id, "tags": [style_tag]},
        )
    return user_id


def _select_style_tags_as(acting_user_id: str, target_user_id: str) -> list[list[str]]:
    settings = get_settings()
    with psycopg.connect(settings.database_url) as conn, conn.transaction(), conn.cursor() as cur:
        cur.execute("select set_config('role', 'authenticated', true)")
        cur.execute(
            "select set_config('request.jwt.claims', %s, true)",
            (json.dumps({"sub": acting_user_id}),),
        )
        cur.execute("select style_tags from user_profile where user_id = %s", (target_user_id,))
        return [list(row[0]) for row in cur.fetchall()]


def test_user_can_read_their_own_profile_through_rls() -> None:
    user_a = _create_user_with_profile("Classic")

    rows = _select_style_tags_as(acting_user_id=user_a, target_user_id=user_a)

    assert rows == [["Classic"]]


def test_user_a_cannot_read_user_bs_profile_through_rls() -> None:
    user_a = _create_user_with_profile("Classic")
    user_b = _create_user_with_profile("Bold")

    rows = _select_style_tags_as(acting_user_id=user_a, target_user_id=user_b)

    assert rows == []
