"""Output grounding guardrail.

A safety net on top of, not a replacement for, the existing deterministic
selection guarantee (constitution Principle IV): every item in a
suggested outfit already only ever comes from the requester's own
wardrobe (`generate_outfits`/`is_slot_complete` in `pipeline/graph.py`).
This module is the explicit, automatic check that catches it if that
guarantee is ever violated by a bug.
"""

from __future__ import annotations

from ..schema import WardrobeItem


def verify_outfit_grounding(
    item_ids: list[str],
    wardrobe_by_id: dict[str, WardrobeItem],
    catalog_ids: set[str],
) -> bool:
    """True iff every item id genuinely exists in the requester's own
    wardrobe or the shared catalog (constitution Principle IV, checked
    literally). No outfit can contain a catalog-only item today (catalog
    substitution is deferred) — checking it anyway costs one cheap
    membership test, not a redesign."""
    return all(item_id in wardrobe_by_id or item_id in catalog_ids for item_id in item_ids)
