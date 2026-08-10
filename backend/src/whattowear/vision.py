"""Photo -> garment detection and attribute extraction.

One structured-output VLM call over a photo that may contain several
garments (a flat-lay, a folded stack, an outfit laid out, a single item on
a hanger). Feature 018 (photo-to-items, specs/018-photo-to-items/
research.md §1) replaced the earlier single-item-only
`extract_attributes_from_image` with `detect_garments_from_image`: one call
now returns a LIST of detections, each with its own region within the
photo plus the same nine attribute fields the single-item version always
produced — not a detection call followed by up to 8 per-detection
extraction calls, which would multiply cost and latency for no accuracy
gain. Reuses the exact `get_chat_model(...).with_structured_output(...)`
pattern already used in `pipeline/generator.py` — same gateway config
layer, no second way to call an LLM. This is a metadata-labeling task over
photos the user already chose, not outfit item selection (constitution
Principle II is about the latter).
"""

from __future__ import annotations

import base64
from typing import Any

from langsmith import traceable

from .adapters.llm_gateway import get_chat_model
from .core.config import get_settings
from .prompts import load_prompt
from .schema import BoundingBox, DetectedGarment, ExtractedAttributes

# A hand-written schema, not one derived automatically from
# `ExtractedAttributes` via `with_structured_output(ExtractedAttributes)`.
# `ExtractedAttributes` is all-`Optional` fields (by design — a failed
# field must not block the others), which Pydantic's generated JSON schema
# omits from `required`. The gateway's structured-output mode rejects that
# ("'required' ... including every key in properties. Missing 'category'.")
# — confirmed by reproducing the real `BadRequestError`, and `strict=False`
# does not change this behavior. OpenAI-style structured outputs instead
# expect every property listed in `required`, with optionality expressed
# as a nullable type — so every field here is `["<type>", "null"]`, all
# fields are in `required`. The plain `json_object` response-format mode
# (no schema at all) was tried too and is rejected outright by this
# gateway route regardless of prompt content — this is the only mode that
# works against it for a schema this shape.
_ATTRIBUTES_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": ["string", "null"]},
        "colors": {"type": ["array", "null"], "items": {"type": "string"}},
        "fabric": {"type": ["string", "null"]},
        "warmth": {"type": ["integer", "null"]},
        "formality": {"type": ["string", "null"]},
        "season": {"type": ["array", "null"], "items": {"type": "string"}},
        "pattern": {"type": ["string", "null"]},
        "fit": {"type": ["string", "null"]},
        "background_color": {"type": ["string", "null"]},
    },
    "required": [
        "category",
        "colors",
        "fabric",
        "warmth",
        "formality",
        "season",
        "pattern",
        "fit",
        "background_color",
    ],
    "additionalProperties": False,
}

# Fractions (0-1) of the photo's width/height — resolution-independent, so
# the frontend applies it against the browser's own naturalWidth/
# naturalHeight rather than the backend needing to know the display size
# (specs/018-photo-to-items/research.md §4). Not `BoundingBox`'s own
# Pydantic-generated schema for the same reason `ExtractedAttributes`'
# isn't reused directly above — this is the strict, hand-written shape the
# gateway's structured-output mode actually accepts.
_REGION_SCHEMA = {
    "type": "object",
    "properties": {
        "x": {"type": "number"},
        "y": {"type": "number"},
        "width": {"type": "number"},
        "height": {"type": "number"},
    },
    "required": ["x", "y", "width", "height"],
    "additionalProperties": False,
}

_DETECTION_SCHEMA = {
    "title": "PhotoDetectionResult",
    "type": "object",
    "properties": {
        "detections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "region": _REGION_SCHEMA,
                    "attributes": _ATTRIBUTES_SCHEMA,
                },
                "required": ["region", "attributes"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["detections"],
    "additionalProperties": False,
}


def _image_content_block(image_bytes: bytes, mime_type: str) -> dict:
    """Builds the multimodal content block ChatOpenAI expects for an inline
    image. Pure/deterministic — the seam test_vision.py exercises without a
    live LLM call."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}


def _build_human_message(image_bytes: bytes, mime_type: str) -> list:
    return [
        {"type": "text", "text": "Detect and describe every distinguishable garment in this photo."},
        _image_content_block(image_bytes, mime_type),
    ]


@traceable(name="vision.detect_garments", run_type="chain")
def detect_garments_from_image(image_bytes: bytes, mime_type: str) -> tuple[list[DetectedGarment], bool]:
    """One VLM call. Raises on a genuine call failure (network/gateway
    error) — the caller (`api/v1/routes/closet.py`) maps that to today's
    single-draft fallback behavior, never a 5xx.

    An empty `detections` list is a valid, successful return — "the call
    succeeded and confidently found nothing" is not this function's concern
    to special-case; that decision (and the exception-vs-empty-list
    fallback shape) belongs to the caller (specs/018-photo-to-items/
    research.md §2).

    Returns `(detections, truncated)`. The model is prompted (`prompts/
    vision_system.md`) to order detections by confidence/prominence;
    `wtw_max_detections_per_photo` is enforced here in Python by truncating
    to that many — never in the JSON schema itself, so a model that
    over-detects degrades to "keep the most confident N, flag truncated"
    rather than a schema-validation failure (research.md §3).

    Uses `_DETECTION_SCHEMA` (a hand-written nullable-required schema, see
    `_ATTRIBUTES_SCHEMA`'s docstring) rather than deriving the schema from
    `DetectedGarment`/`ExtractedAttributes` directly — passing a raw dict
    schema makes `with_structured_output` return a plain dict
    (`JsonOutputParser`, not `PydanticOutputParser`), parsed into
    `DetectedGarment` instances here instead."""
    system_prompt, _version = load_prompt("vision_system")
    llm = get_chat_model(model=get_settings().vision_model, temperature=0.0).with_structured_output(
        _DETECTION_SCHEMA, method="json_schema"
    )
    human = _build_human_message(image_bytes, mime_type)
    raw: Any = llm.invoke([("system", system_prompt), ("human", human)])
    detections = [
        DetectedGarment(region=BoundingBox(**entry["region"]), attributes=ExtractedAttributes(**entry["attributes"]))
        for entry in raw["detections"]
    ]
    max_detections = get_settings().wtw_max_detections_per_photo
    truncated = len(detections) > max_detections
    return detections[:max_detections], truncated
