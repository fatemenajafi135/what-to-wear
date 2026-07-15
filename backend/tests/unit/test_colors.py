"""Unit tests for colors.py (Feature 002 Phase 1 backfill).

Pure functions: hex validation/normalization, palette lookup, nearest-name
derivation, and the WCAG contrast-ratio harmony signal. No I/O.
"""

from __future__ import annotations

import pytest

from whattowear import colors


class TestIsHex:
    @pytest.mark.parametrize("value", ["#1b2a4a", "1b2a4a", "#FFFFFF", "abcdef", "#ABCDEF"])
    def test_accepts_six_digit_hex_with_or_without_hash(self, value):
        assert colors.is_hex(value) is True

    @pytest.mark.parametrize("value", ["#fff", "#12345", "#1234567", "navy", "#12345g", ""])
    def test_rejects_non_six_digit_or_non_hex(self, value):
        assert colors.is_hex(value) is False


class TestNormalizeHex:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("#1B2A4A", "#1b2a4a"),
            ("1b2a4a", "#1b2a4a"),
            ("#FFFFFF", "#ffffff"),
            ("ABCDEF", "#abcdef"),
        ],
    )
    def test_canonicalizes_to_lowercase_with_hash(self, value, expected):
        assert colors.normalize_hex(value) == expected

    def test_rejects_invalid_hex(self):
        with pytest.raises(ValueError):
            colors.normalize_hex("navy")


class TestNameToHex:
    def test_known_name_case_insensitive_and_trimmed(self):
        assert colors.name_to_hex("Navy") == "#1b2a4a"
        assert colors.name_to_hex("  navy  ") == "#1b2a4a"

    def test_unknown_name_raises_keyerror(self):
        with pytest.raises(KeyError):
            colors.name_to_hex("chartreuse-of-the-void")


class TestNearestName:
    def test_exact_palette_hex_maps_to_its_own_name(self):
        assert colors.nearest_name("#000000") == "black"
        assert colors.nearest_name("#ffffff") == "white"

    def test_near_hex_maps_to_closest_palette_name(self):
        # a hair off pure black -> still "black"
        assert colors.nearest_name("#010101") == "black"

    def test_nearest_names_maps_a_list(self):
        assert colors.nearest_names(["#000000", "#ffffff"]) == ["black", "white"]


class TestContrastRatio:
    def test_identical_colors_ratio_is_one(self):
        assert colors.contrast_ratio("#808080", "#808080") == pytest.approx(1.0)

    def test_black_vs_white_is_maximal(self):
        assert colors.contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)

    def test_ratio_is_symmetric(self):
        assert colors.contrast_ratio("#1b2a4a", "#c8ad7f") == pytest.approx(colors.contrast_ratio("#c8ad7f", "#1b2a4a"))


class TestContrastHint:
    def test_high_contrast_pair(self):
        assert "high contrast" in colors.contrast_hint("#000000", "#ffffff")

    def test_low_contrast_pair(self):
        assert "low contrast" in colors.contrast_hint("#808080", "#808080")

    def test_moderate_contrast_pair(self):
        # engineered to land in [2.0, 4.5): this grey vs black is ~3:1
        hint = colors.contrast_hint("#595959", "#000000")
        assert 2.0 <= colors.contrast_ratio("#595959", "#000000") < 4.5
        assert "moderate contrast" in hint
