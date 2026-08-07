"""Unit tests for schema.py — this module never had one (inventory §2).

Focuses on the validators and invariants: hex normalization on write,
warmth bounds, and ScoredOutfit's "exactly one score per dimension" guard,
since those are the places a silent regression could slip through
(a raw string surviving un-normalized, an out-of-range warmth, a missing
or duplicated dimension score corrupting rank_score).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from whattowear.schema import (
    SCORE_DIMENSIONS,
    Context,
    CreateWardrobeItemFromUploadRequest,
    DimensionScore,
    ExtractedAttributes,
    ScoredOutfit,
    WardrobeItem,
    WardrobeItemPatch,
)


class TestWardrobeItem:
    def test_colors_normalized_to_lowercase_hash_hex(self) -> None:
        item = WardrobeItem(id="w1", category="top", colors=["1B2A4A"], formality="casual", warmth=1)
        assert item.colors == ["#1b2a4a"]

    def test_invalid_color_raises(self) -> None:
        with pytest.raises(ValidationError):
            WardrobeItem(id="w1", category="top", colors=["navy"], formality="casual", warmth=1)

    @pytest.mark.parametrize("warmth", [-1, 6])
    def test_warmth_out_of_range_raises(self, warmth: int) -> None:
        with pytest.raises(ValidationError):
            WardrobeItem(id="w1", category="top", colors=[], formality="casual", warmth=warmth)

    def test_defaults(self) -> None:
        item = WardrobeItem(id="w1", category="top", formality="casual", warmth=0)
        assert item.colors == []
        assert item.season == []
        assert item.fabric is None
        assert item.name is None
        assert item.notes is None

    def test_name_and_notes_accepted_when_provided(self) -> None:
        item = WardrobeItem(
            id="w1", category="top", formality="casual", warmth=0, name="Navy tee", notes="Slightly faded"
        )
        assert item.name == "Navy tee"
        assert item.notes == "Slightly faded"


class TestWardrobeItemPatch:
    def test_all_fields_optional(self) -> None:
        patch = WardrobeItemPatch()
        assert patch.category is None
        assert patch.colors is None
        assert patch.name is None
        assert patch.notes is None

    def test_none_colors_pass_through_unvalidated(self) -> None:
        patch = WardrobeItemPatch(colors=None)
        assert patch.colors is None

    def test_present_colors_still_normalized(self) -> None:
        patch = WardrobeItemPatch(colors=["ABCDEF"])
        assert patch.colors == ["#abcdef"]

    def test_name_and_notes_present_when_provided(self) -> None:
        patch = WardrobeItemPatch(name="Navy tee", notes="Slightly faded")
        assert patch.name == "Navy tee"
        assert patch.notes == "Slightly faded"


class TestExtractedAttributes:
    def test_every_field_optional_for_a_failed_extraction(self) -> None:
        attrs = ExtractedAttributes()
        assert attrs.category is None
        assert attrs.colors is None

    def test_colors_normalized_when_present(self) -> None:
        attrs = ExtractedAttributes(colors=["1B2A4A"])
        assert attrs.colors == ["#1b2a4a"]


class TestCreateWardrobeItemFromUploadRequest:
    """Feature 006. The review card's Color field is a NAME (`nearest_names`
    pre-fill), not hex — unlike WardrobeItem/WardrobeItemPatch, this is the
    one write path that must resolve a name to hex itself
    (design-decisions.md §23.4, research.md §5)."""

    def test_formality_warmth_and_season_are_required(self) -> None:
        """Reversal of design-decisions §23.3, per §30: these were optional,
        the frontend stopped sending them, and the write path substituted
        constants — so every scanned item stored the same fabricated
        formality/warmth/season. A missing one must now fail loudly."""
        with pytest.raises(ValidationError):
            CreateWardrobeItemFromUploadRequest(photo_path="user-a/x.jpg", category="top", colors=["navy"])

    def test_fabric_pattern_and_fit_stay_optional(self) -> None:
        req = CreateWardrobeItemFromUploadRequest(
            photo_path="user-a/x.jpg",
            category="top",
            colors=["navy"],
            formality="casual",
            warmth=2,
            season=["spring"],
        )
        assert req.fabric is None
        assert req.pattern is None
        assert req.fit is None

    def test_color_name_resolves_to_hex(self) -> None:
        req = CreateWardrobeItemFromUploadRequest(
            photo_path="user-a/x.jpg",
            category="top",
            colors=["navy"],
            formality="casual",
            warmth=2,
            season=["spring"],
        )
        assert req.colors == ["#1b2a4a"]

    def test_color_hex_passes_through_normalized(self) -> None:
        req = CreateWardrobeItemFromUploadRequest(
            photo_path="user-a/x.jpg",
            category="top",
            colors=["1B2A4A"],
            formality="casual",
            warmth=2,
            season=["spring"],
        )
        assert req.colors == ["#1b2a4a"]

    def test_unrecognized_color_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateWardrobeItemFromUploadRequest(
                photo_path="user-a/x.jpg",
                category="top",
                colors=["mauve"],
                formality="casual",
                warmth=2,
                season=["spring"],
            )

    def test_empty_colors_raises(self) -> None:
        with pytest.raises(ValidationError):
            CreateWardrobeItemFromUploadRequest(
                photo_path="user-a/x.jpg",
                category="top",
                colors=[],
                formality="casual",
                warmth=2,
                season=["spring"],
            )

    def test_name_and_notes_optional(self) -> None:
        req = CreateWardrobeItemFromUploadRequest(
            photo_path="user-a/x.jpg",
            category="top",
            colors=["navy"],
            formality="casual",
            warmth=2,
            season=["spring"],
        )
        assert req.name is None
        assert req.notes is None


class TestContext:
    def test_defaults(self) -> None:
        ctx = Context(occasion="office", formality="business_casual")
        assert ctx.wardrobe == []
        assert ctx.user_id is None
        assert ctx.temp_band is None


class TestScoredOutfit:
    def _scores(self, dims: list[str]) -> list[DimensionScore]:
        return [DimensionScore(dimension=d, value=0.5, reason="test") for d in dims]  # type: ignore[arg-type]

    def test_exactly_one_score_per_dimension_is_valid(self) -> None:
        outfit = ScoredOutfit(items=["w1"], rationale=[], scores=self._scores(list(SCORE_DIMENSIONS)), rank_score=1.0)
        assert len(outfit.scores) == len(SCORE_DIMENSIONS)

    def test_missing_dimension_raises(self) -> None:
        with pytest.raises(ValidationError):
            ScoredOutfit(items=["w1"], rationale=[], scores=self._scores(list(SCORE_DIMENSIONS)[:-1]), rank_score=1.0)

    def test_duplicated_dimension_raises(self) -> None:
        dims = [*SCORE_DIMENSIONS[:-1], SCORE_DIMENSIONS[0]]
        with pytest.raises(ValidationError):
            ScoredOutfit(items=["w1"], rationale=[], scores=self._scores(dims), rank_score=1.0)

    def test_dimension_value_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            DimensionScore(dimension=SCORE_DIMENSIONS[0], value=1.5, reason="test")
