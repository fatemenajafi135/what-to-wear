"""Shared pytest fixtures.

`db_session` runs each test inside an outer transaction that's rolled back on
teardown (the standard SQLAlchemy "join a session into an external
transaction" pattern), so CRUD tests can hit the real Supabase database
without leaving rows behind or colliding with already-seeded data. There is
no separate test database in this solo-scale project (research.md), so
tests isolate via rollback instead.
"""

from __future__ import annotations

import pytest
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
