"""Unit tests for scoring/silhouette_balance.py (Feature 002 Phase 2)."""

from __future__ import annotations

from whattowear.schema import Context, WardrobeItem
from whattowear.scoring import silhouette_balance


def _item(id, category, *, fit=None) -> WardrobeItem:
    return WardrobeItem(
        id=id, category=category, colors=["#000000"],
        formality="casual", warmth=1, season=["summer"], fit=fit,
    )


def _ctx() -> Context:
    return Context(occasion="dinner", formality="casual")


class TestSilhouetteBalanceScore:
    def test_deterministic_no_body_shape_input_required(self):
        items = [_item("t", "top", fit="loose"), _item("j", "jeans", fit="fitted")]
        ctx = _ctx()
        first = silhouette_balance.score(items, ctx)
        second = silhouette_balance.score(items, ctx)
        assert first == second
        # nothing about the request or a user body attribute is consulted
        assert "body" not in first.reason.lower()

    def test_contrasting_fit_scores_higher_than_matching_loose(self):
        contrast = silhouette_balance.score(
            [_item("t", "top", fit="loose"), _item("j", "jeans", fit="fitted")], _ctx()
        )
        both_loose = silhouette_balance.score(
            [_item("t", "top", fit="oversized"), _item("j", "jeans", fit="relaxed")], _ctx()
        )
        assert contrast.value > both_loose.value

    def test_missing_fit_data_is_neutral(self):
        result = silhouette_balance.score([_item("t", "top"), _item("j", "jeans")], _ctx())
        assert result.value == 0.5

    def test_no_top_bottom_pairing_is_neutral(self):
        result = silhouette_balance.score([_item("d", "dress", fit="fitted")], _ctx())
        assert result.value == 0.5

    def test_reason_is_present(self):
        result = silhouette_balance.score(
            [_item("t", "top", fit="loose"), _item("j", "jeans", fit="fitted")], _ctx()
        )
        assert result.reason
