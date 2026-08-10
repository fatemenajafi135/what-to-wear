"""Unit tests for photo -> garment detection and attribute extraction.

Covers the deterministic parts only (payload building, cap enforcement)
plus the LLM-call seam with the model mocked — no live gateway call, no
network. Extraction quality against real photos is the golden-set check
(whattowear.eval.vision_harness), not this file.
"""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest

from whattowear import vision
from whattowear.schema import BoundingBox, DetectedGarment, ExtractedAttributes


def _raw_detection(x: float = 0.0, category: str = "top") -> dict:
    return {
        "region": {"x": x, "y": 0.0, "width": 0.4, "height": 0.6},
        "attributes": {
            "category": category,
            "colors": ["#1b2a4a"],
            "fabric": None,
            "warmth": 2,
            "formality": "smart_casual",
            "season": None,
            "pattern": None,
            "fit": None,
            "background_color": None,
        },
    }


def test_image_content_block_encodes_base64_data_url():
    block = vision._image_content_block(b"fake-bytes", "image/png")

    assert block["type"] == "image_url"
    url = block["image_url"]["url"]
    assert url.startswith("data:image/png;base64,")
    encoded = url.split(",", 1)[1]
    assert base64.b64decode(encoded) == b"fake-bytes"


def test_build_human_message_has_text_then_image():
    message = vision._build_human_message(b"fake-bytes", "image/jpeg")

    assert len(message) == 2
    assert message[0]["type"] == "text"
    assert message[1]["type"] == "image_url"
    assert message[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def _mock_llm(raw: dict) -> MagicMock:
    fake_structured_llm = MagicMock()
    fake_structured_llm.invoke.return_value = raw
    fake_chat_model = MagicMock()
    fake_chat_model.with_structured_output.return_value = fake_structured_llm
    return fake_chat_model


def test_detect_garments_returns_one_detection_per_entry():
    """One VLM call, not a detect-then-extract split (research.md §1) — the
    hand-written `_DETECTION_SCHEMA` dict (method="json_schema") is what's
    passed to `with_structured_output`, so the call returns a plain dict,
    parsed into `DetectedGarment` instances here."""
    raw = {"detections": [_raw_detection(x=0.0, category="t-shirt"), _raw_detection(x=0.5, category="jeans")]}
    fake_chat_model = _mock_llm(raw)

    with patch.object(vision, "get_chat_model", return_value=fake_chat_model):
        detections, truncated = vision.detect_garments_from_image(b"fake-bytes", "image/jpeg")

    assert len(detections) == 2
    assert detections[0] == DetectedGarment(
        region=BoundingBox(x=0.0, y=0.0, width=0.4, height=0.6),
        attributes=ExtractedAttributes(**_raw_detection(category="t-shirt")["attributes"]),
    )
    assert detections[1].attributes.category == "jeans"
    assert truncated is False
    fake_chat_model.with_structured_output.assert_called_once_with(vision._DETECTION_SCHEMA, method="json_schema")


def test_detect_garments_empty_list_is_not_an_error():
    """The call succeeding with zero confident detections is a valid,
    successful return — never raised, and distinct from a genuine call
    failure (research.md §2, the caller's fallback logic depends on this
    distinction)."""
    fake_chat_model = _mock_llm({"detections": []})

    with patch.object(vision, "get_chat_model", return_value=fake_chat_model):
        detections, truncated = vision.detect_garments_from_image(b"fake-bytes", "image/jpeg")

    assert detections == []
    assert truncated is False


def test_detect_garments_enforces_cap_in_python(monkeypatch: pytest.MonkeyPatch):
    """The cap is enforced in Python, not the JSON schema (research.md §3)
    — 9 raw detections keeps the first 8 (the model is prompted to order by
    confidence) and sets truncated."""
    from whattowear.core.config import get_settings

    monkeypatch.setenv("WTW_MAX_DETECTIONS_PER_PHOTO", "8")
    get_settings.cache_clear()
    # Distinct categories: identical ones would now also collapse via
    # `_merge_matching_pairs` (feature 018 follow-up), which is correct
    # behavior for 9 copies of one item but not what this test means to
    # exercise — it means 9 DIFFERENT garments, only the cap in play.
    raw = {"detections": [_raw_detection(x=i / 10, category=f"top-{i}") for i in range(9)]}
    fake_chat_model = _mock_llm(raw)

    with patch.object(vision, "get_chat_model", return_value=fake_chat_model):
        detections, truncated = vision.detect_garments_from_image(b"fake-bytes", "image/jpeg")

    assert len(detections) == 8
    assert truncated is True
    get_settings.cache_clear()


def test_detect_garments_at_exactly_the_cap_is_not_truncated(monkeypatch: pytest.MonkeyPatch):
    from whattowear.core.config import get_settings

    monkeypatch.setenv("WTW_MAX_DETECTIONS_PER_PHOTO", "8")
    get_settings.cache_clear()
    raw = {"detections": [_raw_detection(x=i / 10, category=f"top-{i}") for i in range(8)]}
    fake_chat_model = _mock_llm(raw)

    with patch.object(vision, "get_chat_model", return_value=fake_chat_model):
        detections, truncated = vision.detect_garments_from_image(b"fake-bytes", "image/jpeg")

    assert len(detections) == 8
    assert truncated is False
    get_settings.cache_clear()


def test_extracted_attributes_all_fields_optional():
    # extraction failing on every field must not raise -- an all-null
    # instance is a valid, constructable value.
    attrs = ExtractedAttributes()

    assert attrs.category is None
    assert attrs.colors is None
    assert attrs.pattern is None
    assert attrs.fit is None


class TestDuplicateDetectionFilter:
    """The failure this filter exists for: ordinary single-garment product
    shots came back with two near-identical full-frame detections, so one
    skirt became two closet items showing the same photo."""

    @staticmethod
    def _det(x: float, y: float, w: float, h: float, category: str = "skirt") -> DetectedGarment:
        return DetectedGarment(
            region=BoundingBox(x=x, y=y, width=w, height=h),
            attributes=ExtractedAttributes(category=category),
        )

    def test_two_full_frame_detections_collapse_to_one(self) -> None:
        dets = [self._det(0, 0, 1, 1), self._det(0.01, 0.01, 0.98, 0.98)]
        assert len(vision._drop_overlapping(dets)) == 1

    def test_the_first_most_confident_detection_is_the_one_kept(self) -> None:
        first = self._det(0, 0, 1, 1, category="skirt")
        second = self._det(0.02, 0.0, 0.96, 1.0, category="trousers")
        kept = vision._drop_overlapping([first, second])
        assert [d.attributes.category for d in kept] == ["skirt"]

    def test_genuinely_separate_garments_in_a_flat_lay_all_survive(self) -> None:
        """A real flat-lay must not be collapsed — that would reintroduce the
        single-item-per-photo behaviour this feature exists to remove."""
        dets = [
            self._det(0.0, 0.0, 0.45, 0.45),
            self._det(0.55, 0.0, 0.45, 0.45),
            self._det(0.0, 0.55, 0.45, 0.45),
            self._det(0.55, 0.55, 0.45, 0.45),
        ]
        assert len(vision._drop_overlapping(dets)) == 4

    def test_a_side_by_side_pair_is_not_merged_by_geometry(self) -> None:
        """Two earrings side by side barely overlap, so this filter cannot fix
        them — `prompts/vision_system.md` v4 rule 1 is what must. Recorded so a
        future reader does not expect geometry to solve it."""
        dets = [self._det(0.1, 0.4, 0.3, 0.2, "earrings"), self._det(0.6, 0.4, 0.3, 0.2, "earrings")]
        assert len(vision._drop_overlapping(dets)) == 2

    def test_an_empty_list_is_safe(self) -> None:
        assert vision._drop_overlapping([]) == []


class TestPairMerge:
    """Two earrings, non-overlapping regions, side by side — the case
    `_drop_overlapping` cannot catch because the boxes barely intersect."""

    @staticmethod
    def _attrs(category: str = "earrings", colors=("#d9d9d9", "#ffffff"), **kw) -> ExtractedAttributes:
        return ExtractedAttributes(category=category, colors=list(colors) if colors else None, **kw)

    @staticmethod
    def _det(x: float, attrs: ExtractedAttributes) -> DetectedGarment:
        return DetectedGarment(region=BoundingBox(x=x, y=0.1, width=0.25, height=0.4), attributes=attrs)

    def test_a_real_pair_merges_into_one(self) -> None:
        dets = [self._det(0.1, self._attrs()), self._det(0.6, self._attrs())]
        merged = vision._merge_matching_pairs(dets)
        assert len(merged) == 1
        assert merged[0].attributes.category == "earrings"

    def test_merged_region_covers_both_originals(self) -> None:
        left = self._det(0.1, self._attrs())
        right = self._det(0.6, self._attrs())
        merged = vision._merge_matching_pairs([left, right])[0]
        assert merged.region.x <= left.region.x
        assert merged.region.x + merged.region.width >= right.region.x + right.region.width

    def test_different_colors_do_not_merge(self) -> None:
        """Two rings that happen to share a category but not a color are two
        different items, not a pair."""
        dets = [self._det(0.1, self._attrs(colors=("#d9d9d9",))), self._det(0.6, self._attrs(colors=("#c9a227",)))]
        assert len(vision._merge_matching_pairs(dets)) == 2

    def test_missing_colors_do_not_merge(self) -> None:
        """Absent color data means 'can't confirm', not 'assume a match'."""
        dets = [self._det(0.1, self._attrs(colors=None)), self._det(0.6, self._attrs(colors=None))]
        assert len(vision._merge_matching_pairs(dets)) == 2

    def test_different_category_does_not_merge(self) -> None:
        dets = [self._det(0.1, self._attrs(category="earrings")), self._det(0.6, self._attrs(category="necklace"))]
        assert len(vision._merge_matching_pairs(dets)) == 2

    def test_conflicting_fabric_blocks_the_merge(self) -> None:
        dets = [self._det(0.1, self._attrs(fabric="silver")), self._det(0.6, self._attrs(fabric="gold"))]
        assert len(vision._merge_matching_pairs(dets)) == 2

    def test_one_side_missing_fabric_does_not_block_the_merge(self) -> None:
        """A null on one side is 'not extracted', not a disagreement."""
        dets = [self._det(0.1, self._attrs(fabric="silver")), self._det(0.6, self._attrs(fabric=None))]
        assert len(vision._merge_matching_pairs(dets)) == 1

    def test_a_genuine_flat_lay_of_different_items_is_untouched(self) -> None:
        dets = [
            self._det(0.0, self._attrs(category="top", colors=("#ffffff",))),
            self._det(0.5, self._attrs(category="bottom", colors=("#0f0f10",))),
        ]
        assert len(vision._merge_matching_pairs(dets)) == 2

    def test_three_identical_detections_merge_at_most_two(self) -> None:
        """Not a full pairwise cluster, by design — see the function's own
        docstring for why a wider merge is not attempted."""
        dets = [self._det(0.0, self._attrs()), self._det(0.35, self._attrs()), self._det(0.7, self._attrs())]
        assert len(vision._merge_matching_pairs(dets)) == 2

    def test_empty_list_is_safe(self) -> None:
        assert vision._merge_matching_pairs([]) == []
