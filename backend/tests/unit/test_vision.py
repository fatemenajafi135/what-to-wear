"""Unit tests for photo -> attribute extraction (Feature 003: mvp-app, US2).

Covers the deterministic parts only (payload building) plus the LLM-call
seam with the model mocked -- no live gateway call, no network. Extraction
quality against real photos is the golden-set check
(whattowear.eval.vision_harness), not this file.
"""

from __future__ import annotations

import base64

from whattowear import vision
from whattowear.schema import ExtractedAttributes


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


def test_extract_attributes_from_image_returns_structured_output(mocker):
    """Feature 005 US4: `with_structured_output` is called with the
    hand-written `_EXTRACTION_SCHEMA` dict (method="json_schema"), not the
    `ExtractedAttributes` class directly — the gateway rejects the
    class-derived schema for this all-Optional model (research.md §1). The
    call therefore returns a plain dict, parsed into `ExtractedAttributes`
    by `extract_attributes_from_image` itself."""
    raw = {
        "category": "top",
        "colors": ["#1b2a4a"],
        "fabric": None,
        "warmth": 2,
        "formality": "smart_casual",
        "season": None,
        "pattern": None,
        "fit": None,
    }

    fake_structured_llm = mocker.Mock()
    fake_structured_llm.invoke.return_value = raw
    fake_chat_model = mocker.Mock()
    fake_chat_model.with_structured_output.return_value = fake_structured_llm
    mocker.patch.object(vision, "get_chat_model", return_value=fake_chat_model)

    result = vision.extract_attributes_from_image(b"fake-bytes", "image/jpeg")

    assert result == ExtractedAttributes(**raw)
    fake_chat_model.with_structured_output.assert_called_once_with(vision._EXTRACTION_SCHEMA, method="json_schema")
    fake_structured_llm.invoke.assert_called_once()


def test_extracted_attributes_all_fields_optional():
    # FR-006: extraction failing on every field must not raise -- an
    # all-null instance is a valid, constructable value.
    attrs = ExtractedAttributes()

    assert attrs.category is None
    assert attrs.colors is None
    assert attrs.pattern is None
    assert attrs.fit is None
