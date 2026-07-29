"""SQLAlchemy engine/session, constructed lazily on first use.

Connects through the Supabase transaction pooler (Supavisor) — production's
port 6543, or the local CLI's pooler emulation on port 54329 locally (see
specs/002-backend-foundation/research.md §2-3). Transaction-mode pooling
doesn't support server-side prepared statements or session-level state, so
`prepare_threshold=None` disables psycopg3's prepared statements and
`NullPool` avoids holding a long-lived server-side session — carried forward
from the legacy `db.py` docstring that first documented this failure mode
("prepared statement already exists" / "does not exist" errors).

`get_engine()` is `lru_cache`-wrapped rather than a module-level `engine =
create_engine(...)`: a module-level engine would call `create_engine()` (and
therefore read `DATABASE_URL`) at import time, which is the exact defect this
package exists to not reproduce (research.md §1). Importing this module does
nothing; only calling `get_engine()` or `get_session()` does.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from whattowear.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    # SQLAlchemy's bare "postgresql://" scheme defaults to the psycopg2
    # dialect, which isn't a dependency here — this project uses psycopg3.
    # `DATABASE_URL` is written in the ordinary, driver-agnostic form
    # (matching what `.env.example` and `supabase status` both use), so the
    # scheme is rewritten here rather than asking every caller to know the
    # driver-specific spelling.
    url = settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(
        url,
        poolclass=NullPool,
        connect_args={"prepare_threshold": None},
    )


@lru_cache
def _session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a session, closes it after the request."""
    session = _session_factory()()
    try:
        yield session
    finally:
        session.close()
