"""Unit tests for memory/preferences.py — never had one before this port."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from whattowear.memory.preferences import (
    MIN_SIGNAL_COUNT,
    FeedbackRecord,
    ItemSnapshot,
    derive_signals,
)

_T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _item(item_id: str = "i1", category: str = "top", colors: list[str] | None = None, formality: str = "casual"):
    return ItemSnapshot(item_id=item_id, category=category, colors=colors or ["#1b2a4a"], formality=formality)


def _record(verdict: str, items: list[ItemSnapshot], at: datetime = _T0) -> FeedbackRecord:
    return FeedbackRecord(verdict=verdict, item_snapshot=items, created_at=at)  # type: ignore[arg-type]


class TestColorAndCategorySignals:
    def test_repeated_rejection_of_a_color_crosses_threshold(self) -> None:
        feedback = [_record("rejected", [_item(colors=["#1b2a4a"])]) for _ in range(MIN_SIGNAL_COUNT)]
        signals = derive_signals(feedback, {})
        assert any(s.key == "color:#1b2a4a" and s.kind == "color" for s in signals)

    def test_below_threshold_produces_no_signal(self) -> None:
        feedback = [_record("rejected", [_item(colors=["#1b2a4a"])]) for _ in range(MIN_SIGNAL_COUNT - 1)]
        signals = derive_signals(feedback, {})
        assert not any(s.key == "color:#1b2a4a" for s in signals)

    def test_a_like_offsets_a_rejection_net_count(self) -> None:
        # MIN_SIGNAL_COUNT rejections minus 1 like = MIN_SIGNAL_COUNT - 1 net -> below threshold
        feedback = [_record("rejected", [_item(colors=["#1b2a4a"])]) for _ in range(MIN_SIGNAL_COUNT)]
        feedback.append(_record("liked", [_item(colors=["#1b2a4a"])]))
        signals = derive_signals(feedback, {})
        assert not any(s.key == "color:#1b2a4a" for s in signals)

    def test_category_signal_derived_independently_of_color(self) -> None:
        feedback = [_record("rejected", [_item(category="jeans")]) for _ in range(MIN_SIGNAL_COUNT)]
        signals = derive_signals(feedback, {})
        assert any(s.key == "category:jeans" and s.kind == "category" for s in signals)


class TestDismissal:
    def test_dismissed_signal_excluded_until_a_newer_record_reestablishes_it(self) -> None:
        dismissed_at = _T0 + timedelta(days=1)
        feedback = [_record("rejected", [_item(colors=["#1b2a4a"])], at=_T0) for _ in range(MIN_SIGNAL_COUNT)]
        signals = derive_signals(feedback, {"color:#1b2a4a": dismissed_at})
        assert not any(s.key == "color:#1b2a4a" for s in signals)

    def test_records_after_dismissal_reestablish_the_signal(self) -> None:
        dismissed_at = _T0
        newer = _T0 + timedelta(days=1)
        feedback = [_record("rejected", [_item(colors=["#1b2a4a"])], at=newer) for _ in range(MIN_SIGNAL_COUNT)]
        signals = derive_signals(feedback, {"color:#1b2a4a": dismissed_at})
        assert any(s.key == "color:#1b2a4a" for s in signals)


class TestFormalityDrift:
    def test_needs_both_liked_and_rejected_samples(self) -> None:
        # only rejected samples, no liked ones -> can't establish a direction
        feedback = [_record("rejected", [_item(formality="formal")]) for _ in range(MIN_SIGNAL_COUNT)]
        signals = derive_signals(feedback, {})
        assert not any(s.kind == "formality_drift" for s in signals)

    def test_rejecting_formal_liking_casual_drifts_less_formal(self) -> None:
        feedback = [_record("rejected", [_item(formality="formal")]) for _ in range(MIN_SIGNAL_COUNT)]
        feedback += [_record("liked", [_item(formality="casual")]) for _ in range(MIN_SIGNAL_COUNT)]
        signals = derive_signals(feedback, {})
        drift = next(s for s in signals if s.kind == "formality_drift")
        assert drift.detail == "less_formal"

    def test_rejecting_casual_liking_formal_drifts_more_formal(self) -> None:
        feedback = [_record("rejected", [_item(formality="casual")]) for _ in range(MIN_SIGNAL_COUNT)]
        feedback += [_record("liked", [_item(formality="formal")]) for _ in range(MIN_SIGNAL_COUNT)]
        signals = derive_signals(feedback, {})
        drift = next(s for s in signals if s.kind == "formality_drift")
        assert drift.detail == "more_formal"

    def test_small_delta_produces_no_drift_signal(self) -> None:
        # both groups at the same formality -> delta 0
        feedback = [_record("rejected", [_item(formality="smart_casual")]) for _ in range(MIN_SIGNAL_COUNT)]
        feedback += [_record("liked", [_item(formality="smart_casual")]) for _ in range(MIN_SIGNAL_COUNT)]
        signals = derive_signals(feedback, {})
        assert not any(s.kind == "formality_drift" for s in signals)


def test_no_feedback_produces_no_signals() -> None:
    assert derive_signals([], {}) == []
