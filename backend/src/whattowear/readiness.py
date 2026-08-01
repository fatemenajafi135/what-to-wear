"""Closet-readiness gate for the styling chat (feature 008).

Slot-coverage arithmetic the styling route needs *before* deciding whether to
call the pipeline at all — not part of the pipeline itself, so it stays out
of `pipeline/` (constitution Principle I only protects that directory; this
module never touches AI code). See docs/design-decisions.md §11 for the
three-band rule this implements and specs/008-styling-chat/data-model.md for
the exact algorithm.
"""

from __future__ import annotations

from pydantic import BaseModel

from whattowear.categories import group_of
from whattowear.schema import WardrobeItem


class ReadinessResult(BaseModel):
    ready: bool
    sparse: bool
    missing: list[str]


def evaluate_wardrobe_readiness(
    items: list[WardrobeItem],
    min_items: int,
    sparse_threshold: int,
) -> ReadinessResult:
    """Two outfit skeletons: top+bottom+footwear, or full_body+footwear. A
    closet must satisfy at least one *and* clear the item-count floor to be
    ready. `missing` names the closer skeleton's gaps in natural language;
    it's empty when coverage is fine and the count floor is the only thing
    blocking (the frontend falls back to generic copy in that case)."""
    groups = {group_of(item.category) for item in items}
    has_top = "top" in groups
    has_bottom = "bottom" in groups
    has_footwear = "footwear" in groups
    has_full_body = "full_body" in groups

    skeleton_a_ok = has_top and has_bottom and has_footwear
    skeleton_b_ok = has_full_body and has_footwear
    coverage_ok = skeleton_a_ok or skeleton_b_ok
    count_ok = len(items) >= min_items

    ready = coverage_ok and count_ok
    sparse = ready and len(items) < sparse_threshold

    missing: list[str] = []
    if not coverage_ok:
        gaps_a = [
            phrase
            for phrase, present in (
                ("a top", has_top),
                ("a bottom", has_bottom),
                ("a pair of shoes", has_footwear),
            )
            if not present
        ]
        gaps_b = [
            phrase
            for phrase, present in (
                ("a full-body piece like a dress or jumpsuit", has_full_body),
                ("a pair of shoes", has_footwear),
            )
            if not present
        ]
        missing = gaps_a if len(gaps_a) <= len(gaps_b) else gaps_b

    return ReadinessResult(ready=ready, sparse=sparse, missing=missing)
