"""Memory component — per-user state, separate from the shared knowledge base.

Two layers, matching the course (AIE10 session 3):
- **short-term**: a LangGraph `InMemorySaver` checkpointer (thread state). Exposed
  for any graph-based caller; also used here to keep per-thread interaction turns.
  Still in-memory — out of scope for Feature 004 (preference-memory); lost on
  restart, unchanged from before.
- **long-term**: a per-user **style profile** (preferences learned from
  feedback over time). As of Feature 004, this is Postgres-backed, not an
  in-memory store: `get_profile()` derives the profile on read by
  aggregating that user's `suggestion_feedback` rows
  (`memory.preferences.derive_signals()`) rather than reading back
  previously-`put()` values — there is no longer a way to inject an
  arbitrary preference string directly; a preference is only ever learned
  from real recorded feedback (see `api.py`'s `/preferences/feedback`).
  `profile_note(user_id)`'s signature and behavior are unchanged so
  `pipeline/run.py`/`pipeline/generator.py` needed zero changes
  (specs/004-preference-memory/research.md #4).

This is deliberately NOT the knowledge base: the KB is shared fashion rules; this
is private user state. Both are instantiated and visibly used by `recommend()`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from .. import crud
from ..db import SessionLocal
from . import preferences as preference_derivation

# short-term (thread) memory singleton — untouched by Feature 004.
checkpointer = InMemorySaver()
_store = InMemoryStore()


def _history_ns(user_id: str) -> tuple[str, str]:
    return (user_id, "history")


# --- long-term style profile (Postgres-backed, Feature 004) ------------------


def get_profile(user_id: str) -> dict[str, str]:
    """The derived preference profile, projected to the short `key: value`
    shape `profile_note()` joins into a prompt sentence. Opens its own
    short-lived session (no session parameter -- `profile_note()`'s call
    site in `pipeline/run.py` passes none) via `db.SessionLocal()`, same as
    any other non-request-scoped caller (research.md #4)."""
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
