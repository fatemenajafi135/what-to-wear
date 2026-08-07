"""Unit tests for pipeline/context_assembler.py — never had one before this
port. load_wardrobe/assemble_context now take an injected
ports.ClosetRepository (specs/007-ai-port/research.md §1) instead of
opening a DB session directly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from whattowear.pipeline.context_assembler import assemble_context, infer_formality, load_wardrobe
from whattowear.schema import WardrobeItem


def _item(id: str) -> WardrobeItem:
    return WardrobeItem(id=id, category="top", colors=["#000000"], formality="casual", warmth=1, season=[])


class TestInferFormality:
    def test_exact_known_occasion_match(self) -> None:
        assert infer_formality("wedding") == "formal"
        assert infer_formality("office") == "business_casual"

    def test_whole_word_keyword_scan_on_free_text(self) -> None:
        assert infer_formality("wedding party") == "formal"

    def test_homework_does_not_trip_the_work_keyword(self) -> None:
        # whole-word matching, not substring
        assert infer_formality("homework night") == "smart_casual"

    def test_black_tie_multi_word_cue(self) -> None:
        assert infer_formality("black tie gala") == "black_tie"

    def test_most_formal_keyword_wins_on_conflict(self) -> None:
        # "beach" (casual) + "wedding" (formal) -> formal wins, the safer
        # failure mode (under-dressing a formal event is worse)
        assert infer_formality("beach wedding") == "formal"

    def test_no_match_falls_back_to_smart_casual(self) -> None:
        assert infer_formality("a mysterious happening") == "smart_casual"


class TestLoadWardrobe:
    def test_delegates_to_the_injected_repository(self) -> None:
        repo = MagicMock()
        repo.list_wardrobe_items.return_value = [_item("a")]

        result = load_wardrobe("user-1", repo)

        repo.list_wardrobe_items.assert_called_once_with("user-1")
        assert result == [_item("a")]


class TestAssembleContext:
    def test_explicit_wardrobe_override_bypasses_the_repository(self) -> None:
        repo = MagicMock()
        ctx = assemble_context("office", wardrobe=[_item("a")], user_id="user-1", repo=repo)
        repo.list_wardrobe_items.assert_not_called()
        assert ctx.wardrobe == [_item("a")]

    def test_user_id_with_repo_loads_the_wardrobe(self) -> None:
        repo = MagicMock()
        repo.list_wardrobe_items.return_value = [_item("a")]
        ctx = assemble_context("office", user_id="user-1", repo=repo)
        assert ctx.wardrobe == [_item("a")]

    def test_no_user_id_and_no_wardrobe_is_an_empty_closet(self) -> None:
        ctx = assemble_context("office")
        assert ctx.wardrobe == []

    def test_formality_inferred_when_not_provided(self) -> None:
        ctx = assemble_context("wedding")
        assert ctx.formality == "formal"

    def test_explicit_formality_is_not_overridden(self) -> None:
        ctx = assemble_context("wedding", formality="casual")
        assert ctx.formality == "casual"

    def test_location_success_populates_weather_fields(self) -> None:
        with patch("whattowear.external.weather.get_weather") as mock_weather:
            mock_weather.return_value = {
                "temp_c": 5.0,
                "condition": "rain",
                "temp_band": "cold",
                "season": "winter",
            }
            ctx = assemble_context("office", location="London")

        assert ctx.temp_c == 5.0
        assert ctx.condition == "rain"
        assert ctx.temp_band == "cold"
        assert ctx.season == "winter"

    def test_location_failure_falls_back_to_explicit_temp_c(self) -> None:
        with patch("whattowear.external.weather.get_weather", side_effect=RuntimeError("network down")):
            ctx = assemble_context("office", location="Nowhereville", temp_c=5.0)

        assert ctx.temp_c == 5.0
        assert ctx.temp_band == "cold"
        assert ctx.condition is None

    def test_temp_c_without_location_still_bands_and_seasons(self) -> None:
        ctx = assemble_context("office", temp_c=25.0)
        assert ctx.temp_band == "warm"
        assert ctx.season is not None

    def test_no_temp_c_and_no_location_leaves_weather_unset(self) -> None:
        ctx = assemble_context("office")
        assert ctx.temp_c is None
        assert ctx.temp_band is None
        assert ctx.season is None
