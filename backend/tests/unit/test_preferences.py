"""Unit tests for memory/preferences.py's derive_signals() (Feature 004:
preference-memory). No DB — plain dataclasses in, plain dataclasses out,
per the constitution's Quality Bar ("deterministic logic requires unit
tests") and research.md #5.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from whattowear.memory.preferences import (
    MIN_SIGNAL_COUNT,
    FeedbackRecord,
    ItemSnapshot,
    derive_signals,
)

BASE_TIME = datetime(2026, 1, 1, 12, 0, 0)
NAVY = "#1b2a4a"
RED = "#ff0000"

_category_counter = iter(range(1_000_000))


def _record(verdict, colors=None, category=None, formality="casual", at=None, n=1):
    # A fresh, never-repeating category by default so color/formality-only
    # tests don't accidentally also cross the category-signal threshold.
    category = category if category is not None else f"filler-{next(_category_counter)}"
    return FeedbackRecord(
        verdict=verdict,
        item_snapshot=[
            ItemSnapshot(item_id=f"item-{i}", category=category, colors=colors or [], formality=formality)
            for i in range(n)
        ],
        created_at=at or BASE_TIME,
    )


def _at(offset_seconds: int) -> datetime:
    return BASE_TIME + timedelta(seconds=offset_seconds)


class TestColorSignals:
    def test_below_threshold_produces_no_signal(self):
        feedback = [_record("rejected", colors=[NAVY]) for _ in range(MIN_SIGNAL_COUNT - 1)]
        signals = derive_signals(feedback, {})
        assert signals == []

    def test_at_threshold_produces_a_signal(self):
        feedback = [_record("rejected", colors=[NAVY]) for _ in range(MIN_SIGNAL_COUNT)]
        signals = derive_signals(feedback, {})
        assert [s.key for s in signals] == [f"color:{NAVY}"]
        assert signals[0].kind == "color"
        assert signals[0].supporting_count == MIN_SIGNAL_COUNT

    def test_one_contradicting_like_reduces_but_does_not_erase_the_signal(self):
        # reject navy 4x, like navy once -> net 3, still >= MIN_SIGNAL_COUNT
        feedback = [_record("rejected", colors=[NAVY]) for _ in range(4)] + [_record("liked", colors=[NAVY])]
        signals = derive_signals(feedback, {})
        assert [s.key for s in signals] == [f"color:{NAVY}"]
        assert signals[0].supporting_count == 3

    def test_equal_rejections_and_likes_cancel_out(self):
        feedback = [_record("rejected", colors=[NAVY]) for _ in range(3)] + [
            _record("liked", colors=[NAVY]) for _ in range(3)
        ]
        assert derive_signals(feedback, {}) == []

    def test_unrelated_color_does_not_contribute(self):
        feedback = [_record("rejected", colors=[NAVY]) for _ in range(MIN_SIGNAL_COUNT)] + [
            _record("rejected", colors=[RED])
        ]
        signals = derive_signals(feedback, {})
        assert [s.key for s in signals] == [f"color:{NAVY}"]


class TestCategorySignals:
    def test_avoided_category_crosses_threshold(self):
        feedback = [_record("rejected", category="blazer") for _ in range(MIN_SIGNAL_COUNT)]
        signals = derive_signals(feedback, {})
        assert [s.key for s in signals] == ["category:blazer"]
        assert signals[0].kind == "category"


class TestFormalityDrift:
    def test_consistently_rejecting_more_formal_than_liked_yields_less_formal_drift(self):
        feedback = [_record("rejected", formality="formal") for _ in range(MIN_SIGNAL_COUNT)] + [
            _record("liked", formality="casual") for _ in range(MIN_SIGNAL_COUNT)
        ]
        signals = derive_signals(feedback, {})
        drift = next(s for s in signals if s.kind == "formality_drift")
        assert drift.detail == "less_formal"

    def test_consistently_rejecting_less_formal_than_liked_yields_more_formal_drift(self):
        feedback = [_record("rejected", formality="casual") for _ in range(MIN_SIGNAL_COUNT)] + [
            _record("liked", formality="formal") for _ in range(MIN_SIGNAL_COUNT)
        ]
        signals = derive_signals(feedback, {})
        drift = next(s for s in signals if s.kind == "formality_drift")
        assert drift.detail == "more_formal"

    def test_insufficient_liked_samples_yields_no_drift_signal(self):
        feedback = [_record("rejected", formality="formal") for _ in range(MIN_SIGNAL_COUNT)] + [
            _record("liked", formality="casual") for _ in range(MIN_SIGNAL_COUNT - 1)
        ]
        signals = derive_signals(feedback, {})
        assert not any(s.kind == "formality_drift" for s in signals)

    def test_small_delta_yields_no_drift_signal(self):
        # rejected avg = (0 + 0 + 1) / 3 = 0.33, liked avg = 0 -> delta < 1
        feedback = [
            _record("rejected", formality="casual"),
            _record("rejected", formality="casual"),
            _record("rejected", formality="smart_casual"),
        ] + [_record("liked", formality="casual") for _ in range(MIN_SIGNAL_COUNT)]
        signals = derive_signals(feedback, {})
        assert not any(s.kind == "formality_drift" for s in signals)


class TestDismissal:
    def test_dismissed_signal_is_excluded_until_new_feedback_re_establishes_it(self):
        feedback = [_record("rejected", colors=[NAVY], at=_at(i)) for i in range(MIN_SIGNAL_COUNT)]
        dismissed_at = _at(MIN_SIGNAL_COUNT)  # after all existing feedback

        assert derive_signals(feedback, {}) != []
        assert derive_signals(feedback, {f"color:{NAVY}": dismissed_at}) == []

        # new feedback recorded after the dismissal re-establishes the pattern
        feedback_after = feedback + [
            _record("rejected", colors=[NAVY], at=_at(MIN_SIGNAL_COUNT + i + 1)) for i in range(MIN_SIGNAL_COUNT)
        ]
        signals = derive_signals(feedback_after, {f"color:{NAVY}": dismissed_at})
        assert [s.key for s in signals] == [f"color:{NAVY}"]
        # only the post-dismissal records count toward the re-established signal
        assert signals[0].supporting_count == MIN_SIGNAL_COUNT

    def test_dismissal_of_one_signal_does_not_affect_another(self):
        feedback = [_record("rejected", colors=[NAVY]) for _ in range(MIN_SIGNAL_COUNT)] + [
            _record("rejected", category="blazer") for _ in range(MIN_SIGNAL_COUNT)
        ]
        signals = derive_signals(feedback, {f"color:{NAVY}": _at(1000)})
        assert [s.key for s in signals] == ["category:blazer"]


class TestEmptyHistory:
    def test_no_feedback_yields_no_signals(self):
        assert derive_signals([], {}) == []
