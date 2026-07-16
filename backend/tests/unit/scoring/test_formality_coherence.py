"""Unit tests for scoring/formality_coherence.py (Feature 002 Phase 2)."""

from __future__ import annotations

from whattowear.schema import Context, WardrobeItem
from whattowear.scoring import formality_coherence


def _item(id, category="top", *, formality="casual") -> WardrobeItem:
    return WardrobeItem(
        id=id,
        category=category,
        colors=["#000000"],
        formality=formality,
        warmth=1,
        season=["summer"],
    )


def _ctx() -> Context:
    return Context(occasion="dinner", formality="casual")


class TestFormalityCoherenceScore:
    def test_consistent_formality_scores_higher_than_mismatched(self):
        consistent = formality_coherence.score(
            [_item("a", formality="business_casual"), _item("b", "jeans", formality="business_casual")],
            _ctx(),
        )
        mismatched = formality_coherence.score(
            [_item("a", formality="casual"), _item("b", "jeans", formality="black_tie")],
            _ctx(),
        )
        assert consistent.value > mismatched.value

    def test_single_item_is_perfectly_coherent(self):
        result = formality_coherence.score([_item("a", formality="formal")], _ctx())
        assert result.value == 1.0

    def test_deterministic_rescoring_is_identical(self):
        items = [_item("a", formality="casual"), _item("b", "jeans", formality="smart_casual")]
        ctx = _ctx()
        assert formality_coherence.score(items, ctx) == formality_coherence.score(items, ctx)

    def test_reason_is_present(self):
        result = formality_coherence.score([_item("a")], _ctx())
        assert result.reason
