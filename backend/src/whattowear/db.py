"""SQLAlchemy engine/session factory.

Connects through the Supabase transaction pooler (port 6543, Supavisor).
Transaction-mode pooling doesn't support server-side prepared statements or
session-level state, so `prepare_threshold=None` disables psycopg3's prepared
statements and `NullPool` avoids holding a long-lived server-side session —
see research.md -> "Supabase transaction pooler" for the failure mode this
avoids ("prepared statement already exists" / "does not exist" errors).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

load_dotenv()


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is required. Set it in .env (see .env.example).")
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


engine = create_engine(
    _database_url(),
    poolclass=NullPool,
    connect_args={"prepare_threshold": None},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Session:
    """FastAPI dependency: yields a session, closes it after the request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
