"""Unit tests for pipeline/grounding.py (Feature 005 US2/FR-003-005;
`filter_ungrounded_cites` added in fix/007-citation-guard for
constitution Principle IV's citation clause)."""

from __future__ import annotations

import logging

from whattowear.pipeline.generator import GenRationale
from whattowear.pipeline.grounding import filter_ungrounded_cites, verify_outfit_grounding
from whattowear.schema import WardrobeItem


def _item(id: str) -> WardrobeItem:
    return WardrobeItem(id=id, category="t-shirt", colors=["#000000"], formality="casual", warmth=1, season=[])


class TestVerifyOutfitGrounding:
    def test_all_items_owned_passes(self):
        wardrobe_by_id = {"a": _item("a"), "b": _item("b")}
        assert verify_outfit_grounding(["a", "b"], wardrobe_by_id, catalog_ids=set()) is True

    def test_unknown_item_id_fails(self):
        wardrobe_by_id = {"a": _item("a")}
        assert verify_outfit_grounding(["a", "nonexistent"], wardrobe_by_id, catalog_ids=set()) is False

    def test_empty_item_list_passes_vacuously(self):
        assert verify_outfit_grounding([], wardrobe_by_id={}, catalog_ids=set()) is True

    def test_catalog_only_item_still_passes(self):
        """Principle IV: closet OR catalog. No outfit draws from the catalog
        today (Feature 002 Phase 3), but the predicate itself must accept a
        catalog id, not just a wardrobe id."""
        wardrobe_by_id = {"a": _item("a")}
        assert verify_outfit_grounding(["a", "catalog-item-1"], wardrobe_by_id, catalog_ids={"catalog-item-1"}) is True

    def test_item_in_neither_wardrobe_nor_catalog_fails(self):
        wardrobe_by_id = {"a": _item("a")}
        assert verify_outfit_grounding(["a", "ghost"], wardrobe_by_id, catalog_ids={"catalog-item-1"}) is False


class TestFilterUngroundedCites:
    def test_all_cites_grounded_passes_through_unchanged(self):
        rationale = [GenRationale(text="neutral palette", cites=["L1-color-neutral-anchor"])]
        result = filter_ungrounded_cites(rationale, retrieved_rule_ids={"L1-color-neutral-anchor"})
        assert result == rationale

    def test_ungrounded_cite_dropped_not_whole_line(self):
        """A citation typo/hallucination drops only the offending id — the
        rationale text and any other, genuinely-grounded cite on the same
        line survive untouched."""
        rationale = [GenRationale(text="silver metals", cites=["L1-metal-consistency", "L1-three-max"])]
        result = filter_ungrounded_cites(rationale, retrieved_rule_ids={"L1-metal-consistency"})
        assert result == [GenRationale(text="silver metals", cites=["L1-metal-consistency"])]

    def test_all_cites_ungrounded_leaves_honestly_empty_list(self):
        """Matches the deterministic fallback's own convention (Principle
        IV) — an empty `cites` list, never a fabricated one."""
        rationale = [GenRationale(text="hallucinated reason", cites=["L1-three-max"])]
        result = filter_ungrounded_cites(rationale, retrieved_rule_ids=set())
        assert result == [GenRationale(text="hallucinated reason", cites=[])]

    def test_multiple_rationale_lines_filtered_independently(self):
        rationale = [
            GenRationale(text="line one", cites=["good", "bad"]),
            GenRationale(text="line two", cites=["good"]),
        ]
        result = filter_ungrounded_cites(rationale, retrieved_rule_ids={"good"})
        assert result == [
            GenRationale(text="line one", cites=["good"]),
            GenRationale(text="line two", cites=["good"]),
        ]

    def test_empty_rationale_list_returns_empty(self):
        assert filter_ungrounded_cites([], retrieved_rule_ids={"anything"}) == []

    def test_dropped_citation_is_logged(self, caplog):
        rationale = [GenRationale(text="hallucinated reason", cites=["L1-three-max"])]
        with caplog.at_level(logging.WARNING, logger="whattowear.pipeline.grounding"):
            filter_ungrounded_cites(rationale, retrieved_rule_ids=set())
        assert "L1-three-max" in caplog.text
        assert "Dropping ungrounded citation" in caplog.text

    def test_no_log_when_nothing_dropped(self, caplog):
        rationale = [GenRationale(text="grounded reason", cites=["good"])]
        with caplog.at_level(logging.WARNING, logger="whattowear.pipeline.grounding"):
            filter_ungrounded_cites(rationale, retrieved_rule_ids={"good"})
        assert caplog.text == ""
