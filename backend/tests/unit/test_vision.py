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
    raw = {"detections": [_raw_detection(x=i / 10) for i in range(9)]}
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
    raw = {"detections": [_raw_detection(x=i / 10) for i in range(8)]}
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
