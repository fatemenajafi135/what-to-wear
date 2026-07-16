"""Shared pytest fixtures.

`db_session` runs each test inside an outer transaction that's rolled back on
teardown (the standard SQLAlchemy "join a session into an external
transaction" pattern), so CRUD tests can hit the real Supabase database
without leaving rows behind or colliding with already-seeded data. There is
no separate test database in this solo-scale project (research.md), so
tests isolate via rollback instead.

`_flush_suggest_cache` (autouse, Feature 005 US3): `/suggest` now checks a
real Redis cache by default for any fresh request. Several integration test
files (`test_suggest_refinement.py`, `test_suggest_cache.py`, and any
future one) call `/suggest` for the same seeded `EVAL_BASELINE_USER_ID`
with overlapping occasions — without a global flush, an earlier test's
cached result can silently answer a later, unrelated test (discovered via a
real, reproducible cross-test failure: `test_alternatives_returns_a_
different_outfit_set` failing only when run as part of the full suite,
never in isolation). A local fixture in just one test file isn't enough;
this needs to be global, like `db_session`'s rollback isolation.
"""

from __future__ import annotations

import os

import pytest
import redis as redis_lib
from sqlalchemy.orm import Session

from whattowear.db import engine


@pytest.fixture
def db_session():
    connection = engine.connect()
    outer_transaction = connection.begin()
    # create_savepoint: the session's own commit()/rollback() calls operate on
    # a SAVEPOINT nested inside outer_transaction, so seed_catalog()'s internal
    # session.commit() doesn't escape the rollback below.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def _flush_suggest_cache():
    client = redis_lib.Redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
    try:
        client.flushdb()
        yield
        client.flushdb()
    except redis_lib.RedisError:
        # No local Redis in this environment -- /suggest's cache degrades to
        # always-miss on its own (pipeline/cache.py), so there's nothing to
        # flush and nothing to isolate; don't fail every test over it.
        yield
