"""Unit tests for scoring/properties.py (Feature 002 Phase 1 backfill).

These are the machine-checkable outfit-property assertions the eval harness
runs. Expected values are PROPERTIES (min_formality, max_warmth, requires_outer,
forbidden categories/colors), not fixed outfits.
"""

from __future__ import annotations

from whattowear.schema import WardrobeItem
from whattowear.scoring import properties


def _item(id, category, *, formality="casual", warmth=1, colors=None, season=None) -> WardrobeItem:
    return WardrobeItem(
        id=id,
        category=category,
        colors=colors or ["#000000"],
        formality=formality,
        warmth=warmth,
        season=season or ["summer"],
    )


def _wardrobe(*items: WardrobeItem) -> dict[str, WardrobeItem]:
    return {it.id: it for it in items}


class TestOwnedOnly:
    def test_true_when_all_ids_present(self):
        wardrobe = _wardrobe(_item("a", "top"), _item("b", "jeans"))
        assert properties.owned_only(["a", "b"], wardrobe) is True

    def test_false_when_an_id_is_missing(self):
        wardrobe = _wardrobe(_item("a", "top"))
        assert properties.owned_only(["a", "ghost"], wardrobe) is False


class TestWeatherAppropriate:
    def test_false_when_no_core_item(self):
        # only an accessory -> no core garment -> not a real outfit
        wardrobe = _wardrobe(_item("belt", "belt"))
        assert properties.weather_appropriate(["belt"], wardrobe, {}) is False

    def test_requires_outer_satisfied_by_outerwear_group(self):
        wardrobe = _wardrobe(_item("t", "top"), _item("coat", "coat", warmth=2))
        assert properties.weather_appropriate(["t", "coat"], wardrobe, {"requires_outer": True}) is True

    def test_requires_outer_satisfied_by_high_warmth_non_outer(self):
        # a warmth>=3 item counts even if it isn't grouped as outerwear
        wardrobe = _wardrobe(_item("t", "top"), _item("sweater", "sweater", warmth=4))
        assert properties.weather_appropriate(["t", "sweater"], wardrobe, {"requires_outer": True}) is True

    def test_requires_outer_unsatisfied_when_nothing_warm(self):
        wardrobe = _wardrobe(_item("t", "top", warmth=1), _item("j", "jeans", warmth=1))
        assert properties.weather_appropriate(["t", "j"], wardrobe, {"requires_outer": True}) is False

    def test_max_warmth_violation_on_core_item(self):
        wardrobe = _wardrobe(_item("t", "top", warmth=5))
        assert properties.weather_appropriate(["t"], wardrobe, {"max_warmth": 2}) is False

    def test_max_warmth_respected(self):
        wardrobe = _wardrobe(_item("t", "top", warmth=1))
        assert properties.weather_appropriate(["t"], wardrobe, {"max_warmth": 2}) is True


class TestOccasionFit:
    def test_core_within_one_notch_of_floor_passes(self):
        # floor = business_casual (2); smart_casual (1) is exactly one notch below -> ok
        wardrobe = _wardrobe(_item("t", "top", formality="smart_casual"))
        assert properties.occasion_fit(["t"], wardrobe, {"min_formality": "business_casual"}) is True

    def test_two_notches_below_floor_fails(self):
        # floor = business_casual (2); casual (0) is two notches below -> fail
        wardrobe = _wardrobe(_item("t", "top", formality="casual"))
        assert properties.occasion_fit(["t"], wardrobe, {"min_formality": "business_casual"}) is False

    def test_false_when_no_core_item(self):
        wardrobe = _wardrobe(_item("belt", "belt", formality="formal"))
        assert properties.occasion_fit(["belt"], wardrobe, {"min_formality": "casual"}) is False


class TestRespectsExclusions:
    def test_forbidden_category_flagged(self):
        wardrobe = _wardrobe(_item("s", "sneakers"))
        assert properties.respects_exclusions(["s"], wardrobe, {"forbid_categories": ["sneakers"]}) is False

    def test_forbidden_color_matched_on_derived_name_not_hex(self):
        # #000000 derives to "black"; forbidding "black" (a name) must match it
        wardrobe = _wardrobe(_item("t", "top", colors=["#000000"]))
        assert properties.respects_exclusions(["t"], wardrobe, {"forbid_colors": ["black"]}) is False

    def test_clean_outfit_passes(self):
        wardrobe = _wardrobe(_item("t", "top", colors=["#ffffff"]))
        assert (
            properties.respects_exclusions(
                ["t"], wardrobe, {"forbid_categories": ["sneakers"], "forbid_colors": ["black"]}
            )
            is True
        )


class TestCheckOutfit:
    def test_aggregates_all_four_checks(self):
        wardrobe = _wardrobe(_item("t", "top", formality="casual", warmth=1, colors=["#ffffff"]))
        result = properties.check_outfit(["t"], wardrobe, {"min_formality": "casual"})
        assert result == {
            "owned_only": True,
            "weather_appropriate": True,
            "occasion_fit": True,
            "respects_exclusions": True,
        }
