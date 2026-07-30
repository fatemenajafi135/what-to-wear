"""Unit tests for memory/store.py — never had one before this port.

get_profile/profile_note now take an injected ClosetRepository (the
research.md §1 DI fix) instead of opening a DB session directly, so these
run against a fake repository — no database needed.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from whattowear.core.config import get_settings
from whattowear.memory import store
from whattowear.memory.preferences import FeedbackRecord, ItemSnapshot


class _FakeRepo:
    def __init__(self, feedback: list[FeedbackRecord] | None = None) -> None:
        self._feedback = feedback or []

    def list_wardrobe_items(self, user_id: str) -> list:
        return []

    def list_catalog_items(self) -> list:
        return []

    def get_derivation_inputs(self, user_id: str) -> tuple[list[FeedbackRecord], dict]:
        return self._feedback, {}


def _rejected_navy_feedback(count: int) -> list[FeedbackRecord]:
    item = ItemSnapshot(item_id="i1", category="top", colors=["#1b2a4a"], formality="casual")
    return [
        FeedbackRecord(verdict="rejected", item_snapshot=[item], created_at=datetime(2026, 1, 1, tzinfo=UTC))
        for _ in range(count)
    ]


class TestGetProfile:
    def test_no_feedback_is_an_empty_profile(self) -> None:
        assert store.get_profile("u1", _FakeRepo()) == {}

    def test_derived_signal_appears_in_profile(self) -> None:
        repo = _FakeRepo(feedback=_rejected_navy_feedback(3))
        profile = store.get_profile("u1", repo)
        assert profile.get("color:#1b2a4a") == "#1b2a4a"


class TestProfileNote:
    def test_no_user_id_returns_none(self) -> None:
        assert store.profile_note(None, _FakeRepo()) is None

    def test_no_signals_returns_none(self) -> None:
        assert store.profile_note("u1", _FakeRepo()) is None

    def test_signals_joined_into_one_sentence(self) -> None:
        repo = _FakeRepo(feedback=_rejected_navy_feedback(3))
        note = store.profile_note("u1", repo)
        assert note is not None
        assert "color:#1b2a4a" in note


class TestInteractionHistory:
    def test_remember_and_recall_round_trips(self) -> None:
        store.remember_interaction("u-history-1", "thread-a", "summary text")
        recent = store.recent_interactions("u-history-1")
        assert recent[0]["summary"] == "summary text"
        assert recent[0]["thread_id"] == "thread-a"

    def test_no_user_id_is_a_silent_noop(self) -> None:
        # must not raise, must not create a namespace to later collide with
        store.remember_interaction(None, "thread-b", "should not be stored")

    def test_recent_interactions_are_most_recent_first(self) -> None:
        store.remember_interaction("u-history-2", "t1", "first")
        store.remember_interaction("u-history-2", "t2", "second")
        recent = store.recent_interactions("u-history-2", limit=2)
        assert [r["summary"] for r in recent] == ["second", "first"]

    def test_limit_is_respected(self) -> None:
        for i in range(5):
            store.remember_interaction("u-history-3", f"t{i}", f"msg{i}")
        assert len(store.recent_interactions("u-history-3", limit=2)) == 2


class TestGetCheckpointer:
    @pytest.fixture(autouse=True)
    def _reset_singleton(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(store, "_checkpointer", None)
        get_settings.cache_clear()
        yield
        monkeypatch.setattr(store, "_checkpointer", None)
        get_settings.cache_clear()

    def test_falls_back_to_in_memory_saver_when_no_url_reachable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "")
        monkeypatch.setenv("DATABASE_URL_DIRECT", "")
        monkeypatch.setattr(store, "_reachable", lambda url, timeout=5.0: False)
        checkpointer = store.get_checkpointer()
        assert isinstance(checkpointer, InMemorySaver)

    def test_is_a_singleton_across_calls(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "")
        monkeypatch.setenv("DATABASE_URL_DIRECT", "")
        monkeypatch.setattr(store, "_reachable", lambda url, timeout=5.0: False)
        first = store.get_checkpointer()
        second = store.get_checkpointer()
        assert first is second
