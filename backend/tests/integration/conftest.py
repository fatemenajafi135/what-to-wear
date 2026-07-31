"""Fixtures shared by the integration suite only (never loaded for unit tests,
which have no database dependency — see test_whoami.py's own docstring).

`auth.users` and `auth.uid()` are provided natively by a real Supabase project
(local `supabase start` or cloud) — everywhere this codebase actually ships.
On a bare Postgres used only as a Docker-less local/CI fallback for this
feature's development, neither exists yet. `_ensure_auth_stubs` creates the
minimal stand-ins only when they're missing, so it is a genuine no-op against
a real Supabase database (both checks short-circuit) and never touches or
redefines anything Supabase itself owns.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import text

from whattowear.core.db import get_engine


@pytest.fixture(scope="session", autouse=True)
def _ensure_auth_stubs() -> Iterator[None]:
    engine = get_engine()
    with engine.begin() as conn:
        has_users_table = conn.execute(text("select to_regclass('auth.users')")).scalar()
        if has_users_table is None:
            conn.execute(text("create table auth.users (id uuid primary key default gen_random_uuid(), email text)"))
        has_uid_fn = conn.execute(text("select to_regprocedure('auth.uid()')")).scalar()
        if has_uid_fn is None:
            conn.execute(
                text(
                    """
                    create function auth.uid() returns uuid
                    language sql stable
                    as $$
                      select
                        coalesce(
                            nullif(current_setting('request.jwt.claim.sub', true), ''),
                            (nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub')
                        )::uuid
                    $$
                    """
                )
            )
        # Real Supabase grants `authenticated`/`anon` DML on every `public` table by default
        # (its own project-initialization step, separate from any migration) — a bare Postgres
        # fallback has no such default. Re-granting the same privilege on a real Supabase
        # database is a harmless no-op; it never narrows or replaces an existing grant.
        conn.execute(text("grant select, insert, update, delete on all tables in schema public to authenticated"))
    yield
