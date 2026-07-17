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

    @pytest.mark.parametrize(
        "group", ["top", "bottom", "full_body", "outerwear", "footwear", "accessory"]
    )
    def test_group_names_round_trip(self, group):
        """The photo-extraction path (vision.py) stores the bare GROUP name as
        the category, so every group name MUST map to itself — not fall
        through to the accessory default. Regression guard for the bug where
        'bottom'/'footwear'/'full_body' collapsed into 'accessory', leaving
        those outfit slots permanently empty."""
        assert categories.group_of(group) == group

    def test_every_vision_prompt_category_maps_to_a_real_group(self):
        """The exact vocabulary vision.py asks the model to emit must all
        resolve to real slot groups — none may hit the accessory default by
        accident. Ties the taxonomy to what the extractor actually produces."""
        vision_categories = ["top", "bottom", "full_body", "outerwear", "footwear", "accessory"]
        for cat in vision_categories:
            assert categories.group_of(cat) == cat

    @pytest.mark.parametrize("raw", ["Top", " bottom ", "FOOTWEAR", "Full_Body"])
    def test_case_and_whitespace_are_normalized(self, raw):
        assert categories.group_of(raw) == raw.strip().lower()


class TestIsCore:
    @pytest.mark.parametrize("category", ["top", "jeans", "dress", "coat", "sneakers"])
    def test_core_garment_groups_are_core(self, category):
        assert categories.is_core(category) is True

    @pytest.mark.parametrize("category", ["bottom", "full_body", "footwear"])
    def test_bare_core_group_names_are_core(self, category):
        """Photo items stored as a bare group name must be recognized as core
        garments — the bug had them defaulting to 'accessory', so the scorers
        (color/formality/weather use is_core) silently ignored every pant,
        shoe, and dress in a photo closet."""
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
