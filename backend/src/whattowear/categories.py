"""Garment category taxonomy.

`category` on WardrobeItem stays a free string — fashion categories are
numerous and constantly evolving, so a closed enum would always be behind.
This module provides the CANONICAL known categories, grouped, so any code
that needs "is this a core item or an accessory" / "what counts as
footwear" has one place to look, instead of an ad hoc string set per
module.

Unrecognized categories default to "accessory" — the safer failure mode: an
unrecognized item won't wrongly gate a formality/warmth check meant for core
garments (a real bug this replaces: the prototype's original inline
`ACCESSORIES` set in eval/properties.py defaulted anything NOT in a
five-item list to "core", meaning sneakers, boots, and jewelry would all
have silently counted as core items simply for not being explicitly named).

The category-group enum below (`top`, `bottom`, `full_body`, `outerwear`,
`footwear`, `accessory`) is frozen by constitution Principle VI — features
MUST conform to it and MUST NOT rename a group.
"""

from __future__ import annotations

from typing import Literal

CategoryGroup = Literal["top", "bottom", "full_body", "outerwear", "footwear", "accessory"]

# category -> group. Extend this as new categories show up in data — don't
# invent a parallel classification elsewhere (wardrobe fixtures, prompts, eval
# checks should all read this, not their own string sets).
CATEGORY_GROUPS: dict[str, CategoryGroup] = {
    # tops
    "top": "top",
    "t-shirt": "top",
    "tank_top": "top",
    "blouse": "top",
    "shirt": "top",
    "hoodie": "top",
    "sweatshirt": "top",
    "turtleneck": "top",
    "vest": "top",
    "dress_shirt": "top",
    "polo": "top",
    "sweater": "top",
    "cardigan": "top",
    # bottoms
    "trousers": "bottom",
    "chinos": "bottom",
    "jeans": "bottom",
    "shorts": "bottom",
    "linen_trousers": "bottom",
    "skirt": "bottom",
    "leggings": "bottom",
    "joggers": "bottom",
    "culottes": "bottom",
    # full-body (top+bottom in one piece)
    "dress": "full_body",
    "gown": "full_body",
    "suit": "full_body",
    "jumpsuit": "full_body",
    "romper": "full_body",
    "overalls": "full_body",
    # outerwear
    "blazer": "outerwear",
    "outerwear": "outerwear",
    "coat": "outerwear",
    "jacket": "outerwear",
    "trench_coat": "outerwear",
    "parka": "outerwear",
    "puffer": "outerwear",
    "raincoat": "outerwear",
    # footwear
    "shoes": "footwear",
    "sneakers": "footwear",
    "sandals": "footwear",
    "heels": "footwear",
    "loafers": "footwear",
    "boots": "footwear",
    "flats": "footwear",
    "mules": "footwear",
    "ankle_boots": "footwear",
    "oxfords": "footwear",
    # accessories. "jewelry" was a deliberate umbrella; the specifics below
    # were added when the Add-item review card began asking a user to pick a
    # concrete type within a category (docs/design-decisions.md §31), which
    # an umbrella cannot answer — "an accessory can be a tie, a bow tie, a
    # necklace, a ring". Exactly what this module's docstring invites:
    # new keys mapped to an existing group, nothing downstream changes.
    "belt": "accessory",
    "scarf": "accessory",
    "hat": "accessory",
    "gloves": "accessory",
    "bag": "accessory",
    "jewelry": "accessory",
    "sunglasses": "accessory",
    "tie": "accessory",
    "watch": "accessory",
    "bow_tie": "accessory",
    "necklace": "accessory",
    "ring": "accessory",
    "earrings": "accessory",
    "bracelet": "accessory",
    "brooch": "accessory",
    "socks": "accessory",
    "tights": "accessory",
    # The six GROUP names must also map to themselves. The photo-extraction
    # path (vision.py) prompts the model for a bare group name, so items are
    # stored as 'bottom'/'footwear'/'full_body'/'accessory' — those must
    # round-trip, not fall through to the accessory default (which silently
    # collapsed every photo bottom/shoe/dress into 'accessory', leaving the
    # bottom/footwear slots empty so no outfit could ever be assembled).
    # ('top' and 'outerwear' already round-trip via the entries above.)
    "bottom": "bottom",
    "full_body": "full_body",
    "footwear": "footwear",
    "accessory": "accessory",
}

CORE_GROUPS: frozenset[str] = frozenset({"top", "bottom", "full_body", "outerwear", "footwear"})


def specifics_by_group() -> dict[str, list[str]]:
    """`{group: [specific categories]}`, excluding the six group names that
    map to themselves.

    Exists so the Add-item review card can offer the concrete types that
    belong to a chosen category — a user picks "Accessory", then "bow tie" —
    without the frontend hand-mirroring this table. The colour palette is
    already mirrored by hand with a "keep in sync" comment, and this map
    changes far more often; a second hand-copy would drift. Served by
    `GET /api/v1/taxonomy/categories` (constitution VII: one source of
    truth, no duplicate definition elsewhere)."""
    grouped: dict[str, list[str]] = {group: [] for group in CATEGORY_GROUPS.values()}
    for category, group in CATEGORY_GROUPS.items():
        if category not in grouped:  # skip the self-mapping group names
            grouped[group].append(category)
    return {group: sorted(values) for group, values in sorted(grouped.items())}


def group_of(category: str) -> CategoryGroup:
    """Map a category to its outfit-slot group. Input is normalized for
    case/whitespace, and both a specific garment type ('chinos') and a bare
    group name ('bottom', as the photo-extraction path stores it) resolve
    correctly. Genuinely unrecognized categories still default to
    'accessory' — see module docstring."""
    return CATEGORY_GROUPS.get(category.strip().lower(), "accessory")


def is_core(category: str) -> bool:
    """Core = required for a complete outfit (top/bottom/full_body/outerwear/
    footwear). Accessories (belt, jewelry, bag, ...) are optional extras, not
    outfit-completeness items."""
    return group_of(category) in CORE_GROUPS


def is_accessory(category: str) -> bool:
    return not is_core(category)
