"""GET /api/v1/taxonomy/categories — the category vocabulary, grouped.

Exists so the Add-item review card can offer the concrete garment types that
belong to a chosen category ("Accessory" -> tie, bow tie, necklace, ring)
without the frontend hand-mirroring `categories.CATEGORY_GROUPS`. That table
changes whenever new categories show up in data, and a hand-copy would drift
— the colour palette is already mirrored by hand with a "keep in sync"
comment, and one of those is enough (constitution VII).

Unauthenticated on purpose: it is a static, public vocabulary with nothing
user-specific in it, and the Add screen needs it before any per-user data
loads.
"""

from __future__ import annotations

from fastapi import APIRouter

from whattowear.categories import specifics_by_group

router = APIRouter()


@router.get("/taxonomy/categories")
def get_category_taxonomy() -> dict[str, list[str]]:
    """`{group: [specific categories]}`. The six group names themselves are
    excluded — they are the keys, and offering "top" as a type within "top"
    would be noise. A caller that genuinely has no better answer stores the
    bare group name, which `categories.group_of` round-trips."""
    return specifics_by_group()
