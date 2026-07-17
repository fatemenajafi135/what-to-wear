"""Deterministic outfit-coherence guards.

Moved verbatim out of `pipeline/graph.py` (Feature 010, WP2) so both
`pipeline/graph.py` (the existing `generate_outfits` path) and
`pipeline/engine.py` (the new deterministic-enumeration path) can import
these without a circular import — `graph.py` needs to import `engine.py`'s
node functions, and `engine.py` needs these guards, so they can't live in
either of those two modules. Pure move, no edits (per
`docs/claude-code-implementation-spec.md` WP2's own instruction) — semantics
are unchanged everywhere they're used.
"""

from __future__ import annotations

from collections import Counter

from .. import categories
from ..schema import WardrobeItem


def is_slot_complete(items: list[str], wardrobe_by_id: dict[str, WardrobeItem]) -> bool:
    """A complete outfit covers the body: top-or-full_body, bottom-or-
    full_body, and footwear. Missing any -> drop the outfit (FR-011), never
    fill from the catalog."""
    groups = {categories.group_of(wardrobe_by_id[i].category) for i in items if i in wardrobe_by_id}
    has_top_half = "top" in groups or "full_body" in groups
    has_bottom_half = "bottom" in groups or "full_body" in groups
    has_footwear = "footwear" in groups
    return has_top_half and has_bottom_half and has_footwear


def is_valid_combination(items: list[str], wardrobe_by_id: dict[str, WardrobeItem]) -> bool:
    """Deterministic coherence guard on a generated outfit (constitution
    Principle II — the LLM proposes candidates, but Python decides what's
    wearable, not the model). Deliberately LENIENT: it rejects only
    combinations that are essentially never right, so it can't recreate the
    "returns nothing" failure by over-pruning a legitimately layered look.

    Rejects:
      - more than one pair of footwear (the reported shoes+sneakers bug);
      - two full-body pieces, or two separate bottoms (jeans+chinos);
      - a full-body piece worn with a separate bottom (the reported dress+pants
        bug — a dress/suit/jumpsuit is worn on its own).

    Deliberately does NOT restrict (these are real, common looks):
      - multiple tops — t-shirt + cardigan/sweater is layering, and cardigan/
        sweater live in the 'top' group, so a top count is never capped;
      - a top or outerwear over a full-body piece — a cardigan or blazer over a
        dress is normal; only a separate BOTTOM with a full-body is rejected;
      - multiple outerwear — a blazer under a coat.
    """
    groups = Counter(categories.group_of(wardrobe_by_id[i].category) for i in items if i in wardrobe_by_id)
    if groups["footwear"] > 1:
        return False
    if groups["full_body"] > 1 or groups["bottom"] > 1:
        return False
    if groups["full_body"] >= 1 and groups["bottom"] >= 1:
        return False
    return True
