"""Unit tests for pipeline/context_assembler.py (Feature 002 Phase 5, T050a
backfill — a pre-existing gap Feature 001's Known Debt list didn't cover).

Covers the weather-fallback chain (location resolves -> weather lookup
fails -> falls back to temp_c -> falls back to season-only) and the
OCCASION_FORMALITY default lookup. External calls (get_weather, DB-backed
load_wardrobe, and the current-month season fallback) are mocked — this is
a unit test, not an integration test.
"""

from __future__ import annotations

from whattowear.pipeline import context_assembler
from whattowear.schema import WardrobeItem


def _item(id: str) -> WardrobeItem:
    return WardrobeItem(id=id, category="top", colors=["#000000"], formality="casual", warmth=1, season=[])


class TestWeatherFallbackChain:
    def test_no_location_no_temp_c_leaves_weather_unset(self):
        ctx = context_assembler.assemble_context("office")
        assert ctx.temp_c is None
        assert ctx.temp_band is None
        assert ctx.season is None
        assert ctx.condition is None

    def test_temp_c_without_location_derives_band_and_falls_back_to_season(self, mocker):
        mocker.patch.object(context_assembler, "month_to_season", return_value="winter")

        ctx = context_assembler.assemble_context("office", temp_c=5)

        assert ctx.temp_c == 5
        assert ctx.temp_band == "cold"  # temp_to_band(5) — real, deterministic
        assert ctx.season == "winter"
        assert ctx.condition is None  # never set without a successful weather call

    def test_location_success_uses_the_weather_api_values(self, mocker):
        mocker.patch(
            "whattowear.external.weather.get_weather",
            return_value={"temp_c": 22.0, "condition": "clear", "temp_band": "mild", "season": "spring"},
        )

        ctx = context_assembler.assemble_context("office", location="Paris", temp_c=999)

        # the weather API's own values win over a caller-supplied temp_c
        assert ctx.temp_c == 22.0
        assert ctx.condition == "clear"
        assert ctx.temp_band == "mild"
        assert ctx.season == "spring"

    def test_location_failure_falls_back_to_caller_supplied_temp_c(self, mocker):
        mocker.patch("whattowear.external.weather.get_weather", side_effect=ValueError("bad location"))
        mocker.patch.object(context_assembler, "month_to_season", return_value="autumn")

        ctx = context_assembler.assemble_context("office", location="Nowhere", temp_c=20)

        assert ctx.temp_c == 20
        assert ctx.temp_band == "mild"  # temp_to_band(20)
        assert ctx.season == "autumn"
        assert ctx.condition is None  # weather call failed, never populated

    def test_location_failure_without_temp_c_leaves_weather_unset(self, mocker):
        mocker.patch("whattowear.external.weather.get_weather", side_effect=ValueError("bad location"))

        ctx = context_assembler.assemble_context("office", location="Nowhere")

        assert ctx.temp_c is None
        assert ctx.temp_band is None
        assert ctx.season is None
        assert ctx.condition is None


class TestOccasionFormalityDefault:
    def test_known_occasion_gets_its_default_formality(self):
        ctx = context_assembler.assemble_context("office")
        assert ctx.formality == "business_casual"

    def test_another_known_occasion_gets_its_own_default(self):
        ctx = context_assembler.assemble_context("gala")
        assert ctx.formality == "black_tie"

    def test_unknown_occasion_defaults_to_smart_casual(self):
        ctx = context_assembler.assemble_context("hiking")
        assert ctx.formality == "smart_casual"

    def test_explicit_formality_overrides_the_occasion_default(self):
        ctx = context_assembler.assemble_context("office", formality="formal")
        assert ctx.formality == "formal"


class TestWardrobeResolution:
    def test_explicit_wardrobe_is_used_as_is(self, mocker):
        load_spy = mocker.patch.object(context_assembler, "load_wardrobe")
        item = _item("a")

        ctx = context_assembler.assemble_context("office", wardrobe=[item])

        assert ctx.wardrobe == [item]
        load_spy.assert_not_called()

    def test_user_id_without_explicit_wardrobe_loads_from_the_db(self, mocker):
        item = _item("b")
        load_spy = mocker.patch.object(context_assembler, "load_wardrobe", return_value=[item])

        ctx = context_assembler.assemble_context("office", user_id="user-1")

        load_spy.assert_called_once_with("user-1")
        assert ctx.wardrobe == [item]

    def test_no_user_id_and_no_wardrobe_defaults_to_empty(self):
        ctx = context_assembler.assemble_context("office")
        assert ctx.wardrobe == []
