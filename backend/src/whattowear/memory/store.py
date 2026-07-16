"""Memory component — per-user state, separate from the shared knowledge base.

Two layers, matching the course (AIE10 session 3):
- **short-term**: a LangGraph checkpointer (thread state) — `PostgresSaver`
  when a reachable Postgres URL is configured (Feature 002 Phase 4: refinement
  threads must survive process restarts), else `InMemorySaver`. Exposed for
  any graph-based caller; also used here to keep per-thread interaction turns.
- **long-term**: a LangGraph `InMemoryStore` holding a per-user **style profile**
  (preferences learned over time), namespaced `(user_id, "profile")`.

This is deliberately NOT the knowledge base: the KB is shared fashion rules; this
is private user state. Both are instantiated and visibly used by `recommend()`.

Extension seam: swap `InMemoryStore` for a persistent backend with the same API
to make the profile durable too — not done this feature (spec scopes durability
to refinement threads only).
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

    Connects manually with `prepare_threshold=None` rather than using
    PostgresSaver.from_conn_string (which hardcodes `prepare_threshold=0` —
    prepare on first use): that reproduced db.py's own documented
    "prepared statement does not exist" failure even against
    DATABASE_URL_DIRECT, not only the pooler — so the same mitigation
    db.py's SQLAlchemy engine uses applies here too."""
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    direct_url = os.environ.get("DATABASE_URL_DIRECT")
    pooler_url = os.environ.get("DATABASE_URL")
    url = direct_url if _reachable(direct_url) else pooler_url

    if url:
        conn = _checkpointer_stack.enter_context(
            psycopg.connect(url, autocommit=True, prepare_threshold=None, row_factory=dict_row)
        )
        saver = PostgresSaver(conn)
        saver.setup()
        _checkpointer = saver
    else:
        _checkpointer = InMemorySaver()
    return _checkpointer


def _profile_ns(user_id: str) -> tuple[str, str]:
    return (user_id, "profile")


def _history_ns(user_id: str) -> tuple[str, str]:
    return (user_id, "history")


# --- long-term style profile -------------------------------------------------


def set_preference(user_id: str, key: str, value: str) -> None:
    _store.put(_profile_ns(user_id), key, {"value": value, "updated_at": _now()})


def get_profile(user_id: str) -> dict[str, str]:
    return {item.key: item.value["value"] for item in _store.search(_profile_ns(user_id))}


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
