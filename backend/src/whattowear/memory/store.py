"""Memory component — per-user state, separate from the shared knowledge base.

Two layers, matching the course (AIE10 session 3):
- **short-term**: a LangGraph checkpointer (thread state) — `PostgresSaver`
  when a reachable Postgres URL is configured (Feature 002 Phase 4: refinement
  threads must survive process restarts), else `InMemorySaver`. Exposed for
  any graph-based caller; also used here to keep per-thread interaction turns.
- **long-term**: a per-user **style profile** (preferences learned from
  feedback over time). As of Feature 004, this is Postgres-backed, not an
  in-memory store: `get_profile()` derives the profile on read by
  aggregating that user's `suggestion_feedback` rows
  (`memory.preferences.derive_signals()`) rather than reading back
  previously-`put()` values — there is no longer a way to inject an
  arbitrary preference string directly; a preference is only ever learned
  from real recorded feedback (see `api.py`'s `/preferences/feedback`).
  `profile_note(user_id)`'s signature and behavior are unchanged so the
  graph's generation node needed zero changes (specs/004-preference-memory/
  research.md #4).

This is deliberately NOT the knowledge base: the KB is shared fashion rules; this
is private user state.
"""

from __future__ import annotations

import os
from contextlib import ExitStack
from datetime import datetime, timezone
from typing import Optional

import psycopg
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.memory import InMemoryStore
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .. import crud
from ..db import SessionLocal
from . import preferences as preference_derivation

_store = InMemoryStore()

_checkpointer_stack = ExitStack()
_checkpointer: InMemorySaver | PostgresSaver | None = None


def _reachable(url: Optional[str], timeout: float = 5.0) -> bool:
    """Same reachability probe alembic/env.py uses for DATABASE_URL_DIRECT
    (some dev sandboxes can't route to it — IPv6-only) — don't fork the
    fallback logic, just the target (here: the checkpointer connection, not
    a one-shot migration connection)."""
    if not url:
        return False
    try:
        with psycopg.connect(url, connect_timeout=timeout):
            return True
    except psycopg.OperationalError:
        return False


def get_checkpointer() -> InMemorySaver | PostgresSaver:
    """Lazy singleton (mirrors kb.get_kb()/graph.get_compiled_graph()).
    Prefers DATABASE_URL_DIRECT (session-mode, port 5432) over DATABASE_URL
    (the Supavisor transaction pooler, port 6543), then falls back to
    InMemorySaver if neither is configured/reachable (e.g. a dev environment
    without Postgres set up at all).

    Backed by a `ConnectionPool`, NOT a single long-lived connection. The
    process-wide graph singleton reuses one checkpointer across every
    request; a lone connection to the Supabase pooler gets closed on the
    server side after an idle period, so the FIRST /suggest worked and the
    NEXT one raised `OperationalError: the connection is closed` from inside
    `graph.invoke` (checkpointer.get_tuple). The pool checks a connection's
    liveness on checkout (`check=ConnectionPool.check_connection`) and
    transparently discards+replaces a dead one, so an idle drop can never
    surface as a 500.

    Pool connections use `prepare_threshold=None` rather than
    PostgresSaver.from_conn_string's hardcoded `prepare_threshold=0`
    (prepare on first use): that reproduced db.py's own documented
    "prepared statement does not exist" failure even against
    DATABASE_URL_DIRECT, not only the pooler — the same mitigation db.py's
    SQLAlchemy engine uses applies here too."""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    direct_url = os.environ.get("DATABASE_URL_DIRECT")
    pooler_url = os.environ.get("DATABASE_URL")
    url = direct_url if _reachable(direct_url) else pooler_url

    if url:
        pool = ConnectionPool(
            conninfo=url,
            min_size=1,
            max_size=int(os.environ.get("WTW_CHECKPOINTER_POOL_MAX", "5")),
            kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
            check=ConnectionPool.check_connection,
            open=True,
        )
        _checkpointer_stack.callback(pool.close)
        saver = PostgresSaver(pool)
        saver.setup()
        _checkpointer = saver
    else:
        _checkpointer = InMemorySaver()
    return _checkpointer


def _history_ns(user_id: str) -> tuple[str, str]:
    return (user_id, "history")


# --- long-term style profile (Postgres-backed, Feature 004) ------------------


def get_profile(user_id: str) -> dict[str, str]:
    """The derived preference profile, projected to the short `key: value`
    shape `profile_note()` joins into a prompt sentence. Opens its own
    short-lived session (no session parameter -- callers outside a request
    scope pass none) via `db.SessionLocal()`, same as any other
    non-request-scoped caller (research.md #4)."""
    with SessionLocal() as session:
        feedback, dismissals = crud.get_derivation_inputs(session, user_id)
    signals = preference_derivation.derive_signals(feedback, dismissals)
    return {s.key: s.detail for s in signals}


def profile_note(user_id: Optional[str]) -> Optional[str]:
    """A soft-preference sentence injected into the generator, or None."""
    if not user_id:
        return None
    prof = get_profile(user_id)
    if not prof:
        return None
    return "; ".join(f"{k}: {v}" for k, v in prof.items())


# --- short-term interaction history (per thread/user) ------------------------


def remember_interaction(user_id: Optional[str], thread_id: str, summary: str) -> None:
    if not user_id:
        return
    key = f"{thread_id}:{_now()}"
    _store.put(_history_ns(user_id), key, {"thread_id": thread_id, "summary": summary, "at": _now()})


def recent_interactions(user_id: str, limit: int = 5) -> list[dict]:
    items = sorted(_store.search(_history_ns(user_id)), key=lambda it: it.value.get("at", ""), reverse=True)
    return [it.value for it in items[:limit]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
