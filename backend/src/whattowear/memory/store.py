"""Memory component — per-user state, separate from the shared knowledge base.

Two layers, matching the course (AIE10 session 3):
- **short-term**: a LangGraph `InMemorySaver` checkpointer (thread state). Exposed
  for any graph-based caller; also used here to keep per-thread interaction turns.
- **long-term**: a LangGraph `InMemoryStore` holding a per-user **style profile**
  (preferences learned over time), namespaced `(user_id, "profile")`.

This is deliberately NOT the knowledge base: the KB is shared fashion rules; this
is private user state. Both are instantiated and visibly used by `recommend()`.

Extension seam: swap `InMemoryStore`/`InMemorySaver` for persistent backends with
the same API to make the profile durable in production.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

# short-term (thread) + long-term (per-user) memory singletons
checkpointer = InMemorySaver()
_store = InMemoryStore()


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
    items = sorted(
        _store.search(_history_ns(user_id)), key=lambda it: it.value.get("at", ""), reverse=True
    )
    return [it.value for it in items[:limit]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
