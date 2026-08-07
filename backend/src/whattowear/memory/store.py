"""Memory component — per-user state, separate from the shared knowledge base.

Two layers:
- **short-term**: a LangGraph checkpointer (thread state) — `PostgresSaver`
  when a reachable Postgres URL is configured (refinement threads must
  survive process restarts), else `InMemorySaver`. Exposed for any
  graph-based caller; also used here to keep per-thread interaction turns.
- **long-term**: a per-user **style profile** (preferences learned from
  feedback over time). `get_profile()` derives the profile on read by
  aggregating that user's feedback (`memory.preferences.derive_signals()`)
  rather than reading back previously-`put()` values — there is no way to
  inject an arbitrary preference string directly; a preference is only
  ever learned from real recorded feedback.

This is deliberately NOT the knowledge base: the KB is shared fashion
rules; this is private user state.

DB coupling fix (specs/007-ai-port/research.md §1): `get_profile` used to
open its own `SessionLocal()` and call `crud.get_derivation_inputs`
directly — the second of the three documented coupling defects
(docs/legacy-ai-inventory.md §3). It now takes an injected
`ports.ClosetRepository` instead. `get_checkpointer()`'s raw psycopg pool
is untouched: it's LangGraph's own storage backend, not a `SessionLocal`/
ORM concern, and Postgres connection info now comes from
`core.config.get_settings()` instead of a direct `os.environ` read
(consolidating into the one config layer, research.md §10).
"""

from __future__ import annotations

import logging
from contextlib import ExitStack
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import psycopg
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.memory import InMemoryStore
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from ..core.config import get_settings
from . import preferences as preference_derivation

if TYPE_CHECKING:
    from ..ports import ClosetRepository

_store = InMemoryStore()

logger = logging.getLogger(__name__)

_checkpointer_stack = ExitStack()
_checkpointer: InMemorySaver | PostgresSaver | None = None


def _reachable(url: str | None, timeout: float = 5.0) -> bool:
    """Connectivity probe for the checkpointer's target only — not a
    session-factory call, so it isn't the coupling this port fixes."""
    if not url:
        return False
    try:
        with psycopg.connect(url, connect_timeout=int(timeout)):
            return True
    except psycopg.OperationalError:
        return False


def _harden_checkpointer_tables(pool: ConnectionPool[Connection[dict[str, object]]]) -> None:
    """Revoke `authenticated`/`anon` access to LangGraph's checkpointer
    tables and enable RLS on them (with NO policy, so RLS denies by
    default).

    These tables are created by `PostgresSaver.setup()` above, not by a
    migration, so they never passed through `0002`'s RLS-and-GRANT
    convention — and Postgres' default ACL for objects created in `public`
    handed `authenticated` full SELECT/INSERT/UPDATE/DELETE on them. Since
    PostgREST exposes the whole `public` schema, that made every user's
    checkpointed graph state readable and writable by ANY signed-in user
    over `/rest/v1/checkpoints`: `GET /rest/v1/checkpoint_blobs` with a
    brand-new account's token returned other users' rows, and those blobs
    carry the serialized `Context` — wardrobe items with names, colors and
    photo_paths, the caller's `user_id`, and their free-text occasion.
    Confirmed by exploiting it against the local stack, then re-running
    the same probe after this fix.

    Applied here rather than in a migration because the tables do not
    exist until `setup()` has run: a migration would be a silent no-op on
    a database reset from empty, which is precisely the state a fresh
    deploy starts in. Table names are discovered from the catalog rather
    than hardcoded so a future LangGraph release that adds another
    `checkpoint*` table is covered without a code change here.

    Note this does NOT protect against the app's own pooler role, which
    has BYPASSRLS (the same caveat `0002` documents for `wardrobe_items`)
    — it closes the PostgREST path, which was the actual exposure.
    """
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(
            "select tablename from pg_tables where schemaname = 'public' and tablename like 'checkpoint%'",
        )
        tables = [str(row["tablename"]) for row in cur.fetchall()]
        for table in tables:
            # Identifiers can't be parameterized; `table` comes from
            # pg_tables filtered to a literal prefix, never from input.
            cur.execute(f'revoke all on public."{table}" from authenticated, anon')
            cur.execute(f'alter table public."{table}" enable row level security')
    logger.info("Hardened %d checkpointer table(s): RLS enabled, authenticated/anon revoked", len(tables))


def get_checkpointer() -> InMemorySaver | PostgresSaver:
    """Lazy singleton (mirrors kb.get_kb()/graph.get_compiled_graph()).

    Behavior is controlled by wtw_checkpointer_mode (Settings):
    - "memory": explicitly use InMemorySaver (development/testing without Postgres)
    - "auto" (default): use Postgres if DATABASE_URL is reachable; otherwise
      InMemorySaver (for local dev without Postgres)
    - "postgres": require DATABASE_URL to be set and reachable; fail if missing
      (prevents silent fallback to RAM when a cloud service forgets DATABASE_URL)

    When using Postgres, prefers `database_url_direct` (session-mode, port 5432)
    over `database_url` (the Supavisor transaction pooler, port 6543).

    Backed by a `ConnectionPool`, NOT a single long-lived connection. The
    process-wide graph singleton reuses one checkpointer across every request;
    a lone connection to the Supabase pooler gets closed on the server side
    after an idle period, so the FIRST invoke would work and the NEXT one would
    raise `OperationalError: the connection is closed` from inside
    `graph.invoke` (checkpointer.get_tuple). The pool checks a connection's
    liveness on checkout (`check=ConnectionPool.check_connection`) and
    transparently discards+replaces a dead one, so an idle drop can never
    surface as a request failure.

    Pool connections use `prepare_threshold=None` rather than
    `PostgresSaver.from_conn_string`'s hardcoded `prepare_threshold=0`
    (prepare on first use): that reproduces the documented "prepared statement
    does not exist" failure even against the direct URL, not only the pooler —
    the same mitigation `core/db.py`'s SQLAlchemy engine uses applies here too.
    """
    global _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    settings = get_settings()
    mode = settings.wtw_checkpointer_mode.lower()

    # Explicit memory mode: always use InMemorySaver
    if mode == "memory":
        _checkpointer = InMemorySaver()
        return _checkpointer

    # Find the best database URL (prefer direct session-mode connection)
    url = settings.database_url_direct if _reachable(settings.database_url_direct) else settings.database_url

    # "auto" mode: use Postgres if available, fallback to memory
    if mode == "auto":
        if url:
            try:
                pool: ConnectionPool[Connection[dict[str, object]]] = ConnectionPool(
                    conninfo=url,
                    min_size=1,
                    max_size=settings.wtw_checkpointer_pool_max,
                    kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
                    check=ConnectionPool.check_connection,
                    open=True,
                )
                _checkpointer_stack.callback(pool.close)
                saver = PostgresSaver(pool)
                saver.setup()
                _harden_checkpointer_tables(pool)
                _checkpointer = saver
            except Exception as e:
                raise RuntimeError(
                    f"Failed to initialize PostgresSaver in 'auto' mode. Check your database URL configuration: {e}"
                ) from e
        else:
            logger.info(
                "No database URL configured; using InMemorySaver. Set wtw_checkpointer_mode='memory' to silence this."
            )
            _checkpointer = InMemorySaver()
        return _checkpointer

    # "postgres" mode: require database URL and it must be reachable
    if mode == "postgres":
        if not url:
            raise RuntimeError(
                "wtw_checkpointer_mode is 'postgres' but no DATABASE_URL is configured. "
                "Set DATABASE_URL or change wtw_checkpointer_mode to 'auto' or 'memory'."
            )
        try:
            pool: ConnectionPool[Connection[dict[str, object]]] = ConnectionPool(
                conninfo=url,
                min_size=1,
                max_size=settings.wtw_checkpointer_pool_max,
                kwargs={"autocommit": True, "prepare_threshold": None, "row_factory": dict_row},
                check=ConnectionPool.check_connection,
                open=True,
            )
            _checkpointer_stack.callback(pool.close)
            saver = PostgresSaver(pool)
            saver.setup()
            _harden_checkpointer_tables(pool)
            _checkpointer = saver
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialize PostgresSaver in 'postgres' mode. DATABASE_URL must be reachable: {e}"
            ) from e
        return _checkpointer

    # Unknown mode
    raise ValueError(f"Invalid wtw_checkpointer_mode='{mode}'. Must be 'auto', 'memory', or 'postgres'.")


def _history_ns(user_id: str) -> tuple[str, str]:
    return (user_id, "history")


# --- long-term style profile --------------------------------------------


def get_profile(user_id: str, repo: ClosetRepository) -> dict[str, str]:
    """The derived preference profile, projected to the short `key: value`
    shape `profile_note()` joins into a prompt sentence."""
    feedback, dismissals = repo.get_derivation_inputs(user_id)
    signals = preference_derivation.derive_signals(feedback, dismissals)
    return {s.key: s.detail for s in signals}


def profile_note(user_id: str | None, repo: ClosetRepository) -> str | None:
    """A soft-preference sentence injected into the generator, or None."""
    if not user_id:
        return None
    prof = get_profile(user_id, repo)
    if not prof:
        return None
    return "; ".join(f"{k}: {v}" for k, v in prof.items())


# --- short-term interaction history (per thread/user) ------------------------


def remember_interaction(user_id: str | None, thread_id: str, summary: str) -> None:
    if not user_id:
        return
    key = f"{thread_id}:{_now()}"
    _store.put(_history_ns(user_id), key, {"thread_id": thread_id, "summary": summary, "at": _now()})


def recent_interactions(user_id: str, limit: int = 5) -> list[dict]:
    items = sorted(_store.search(_history_ns(user_id)), key=lambda it: it.value.get("at", ""), reverse=True)
    return [it.value for it in items[:limit]]


def _now() -> str:
    return datetime.now(UTC).isoformat()
