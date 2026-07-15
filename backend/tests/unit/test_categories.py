"""Unit tests for categories.py (Feature 002 Phase 1 backfill).

Covers the taxonomy grouping, the core/accessory split, and — critically —
the "unrecognized -> accessory" default that the module docstring calls out as
a deliberate fix (unknown items must NOT silently count as core garments).
"""

from __future__ import annotations

import pytest

from whattowear import categories


class TestGroupOf:
    @pytest.mark.parametrize(
        "category,group",
        [
            ("t-shirt", "top"),
            ("jeans", "bottom"),
            ("dress", "full_body"),
            ("blazer", "outerwear"),
            ("boots", "footwear"),
            ("jewelry", "accessory"),
        ],
    )
    def test_known_categories_map_to_their_group(self, category, group):
        assert categories.group_of(category) == group

    def test_unknown_category_defaults_to_accessory(self):
        assert categories.group_of("space_suit") == "accessory"


class TestIsCore:
    @pytest.mark.parametrize("category", ["top", "jeans", "dress", "coat", "sneakers"])
    def test_core_garment_groups_are_core(self, category):
        assert categories.is_core(category) is True

    @pytest.mark.parametrize("category", ["belt", "scarf", "jewelry", "watch"])
    def test_accessories_are_not_core(self, category):
        assert categories.is_core(category) is False

    def test_unknown_category_is_not_core(self):
        # the docstring's headline guarantee: unknowns default to accessory,
        # so an unrecognized item never gates a core-item formality/warmth check.
        assert categories.is_core("mystery_item") is False


class TestIsAccessory:
    def test_is_accessory_is_negation_of_is_core(self):
        for category in ["top", "belt", "boots", "watch", "unknown_thing"]:
            assert categories.is_accessory(category) == (not categories.is_core(category))
