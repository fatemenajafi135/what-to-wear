"""Unit tests for pipeline/cache.py's key derivation (Feature 005 US3/FR-006/007).

Only `compute_cache_key` (pure) is unit-tested here — `get_cached_result`/
`set_cached_result` need a real Redis and are covered by the integration
test (test_suggest_cache.py).
"""

from __future__ import annotations

from whattowear.pipeline.cache import compute_cache_key
from whattowear.schema import WardrobeItem


def _item(id: str, **overrides) -> WardrobeItem:
    defaults = dict(category="t-shirt", colors=["#000000"], formality="casual", warmth=1, season=[])
    defaults.update(overrides)
    return WardrobeItem(id=id, **defaults)


def _key(**overrides):
    defaults = dict(
        user_id="user-1",
        occasion="office",
        mood=None,
        formality=None,
        location=None,
        temp_c=10.0,
        wardrobe=[_item("a")],
    )
    defaults.update(overrides)
    return compute_cache_key(**defaults)


class TestNormalization:
    def test_casing_and_whitespace_collapse_to_same_key(self):
        assert _key(occasion="Office", mood=" Chill ") == _key(occasion="office", mood="chill")

    def test_different_occasion_yields_different_key(self):
        assert _key(occasion="office") != _key(occasion="wedding")

    def test_explicit_formality_matching_the_default_collapses_to_same_key(self):
        # "office" resolves to business_casual via OCCASION_FORMALITY.
        assert _key(occasion="office", formality=None) == _key(occasion="office", formality="business_casual")


class TestPerUserScoping:
    def test_different_users_never_collapse_to_the_same_key_even_with_identical_inputs(self):
        assert _key(user_id="user-1") != _key(user_id="user-2")


class TestWardrobeFingerprint:
    def test_same_wardrobe_same_key(self):
        assert _key(wardrobe=[_item("a"), _item("b")]) == _key(wardrobe=[_item("a"), _item("b")])

    def test_wardrobe_load_order_does_not_affect_key(self):
        assert _key(wardrobe=[_item("a"), _item("b")]) == _key(wardrobe=[_item("b"), _item("a")])

    def test_added_item_changes_key(self):
        assert _key(wardrobe=[_item("a")]) != _key(wardrobe=[_item("a"), _item("b")])

    def test_removed_item_changes_key(self):
        assert _key(wardrobe=[_item("a"), _item("b")]) != _key(wardrobe=[_item("a")])

    def test_edited_item_attribute_changes_key(self):
        assert _key(wardrobe=[_item("a", warmth=1)]) != _key(wardrobe=[_item("a", warmth=3)])


class TestTemperatureAndLocation:
    def test_nearby_temps_in_the_same_band_collapse_to_same_key(self):
        assert _key(temp_c=9.0) == _key(temp_c=9.5)

    def test_temps_in_different_bands_differ(self):
        assert _key(temp_c=5.0) != _key(temp_c=25.0)

    def test_location_used_when_no_temp_c_given(self):
        assert _key(temp_c=None, location="Paris") != _key(temp_c=None, location="Tokyo")
