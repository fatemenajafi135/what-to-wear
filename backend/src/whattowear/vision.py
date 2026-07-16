"""Photo -> item attribute extraction (Feature 003: mvp-app, US2).

One structured-output VLM call over a single item photo. Reuses the exact
`get_chat_model(...).with_structured_output(...)` pattern already validated in
`pipeline/generator.py` — same gateway config layer, no second way to call an
LLM. This is a metadata-labeling task over a single photo the user already
chose, not outfit item selection (constitution Principle II is about the
latter; see specs/003-mvp-app/plan.md's Constitution Check).
"""

from __future__ import annotations

import base64
import os

from langsmith import traceable

from .config import CHAT_MODEL, get_chat_model
from .schema import ExtractedAttributes

VISION_MODEL = os.environ.get("WTW_VISION_MODEL", CHAT_MODEL)

SYSTEM_PROMPT = (
    "You are a garment attribute extractor. Given a photo of a single clothing "
    "item or accessory, extract:\n"
    "- category: one of top, bottom, full_body, outerwear, footwear, accessory\n"
    "- colors: dominant color(s) as hex strings\n"
    "- fabric: e.g. cotton, denim, wool, leather, knit\n"
    "- warmth: integer 0 (airy) to 5 (heaviest)\n"
    "- formality: one of casual, smart_casual, business_casual, semi_formal, formal, black_tie\n"
    "- season: one or more of spring, summer, autumn, winter\n"
    "- pattern: e.g. solid, striped, plaid, floral, print\n"
    "- fit: e.g. slim, regular, relaxed, oversized\n"
    "If the photo doesn't clearly show a garment, or you can't confidently "
    "determine a field, leave that field null rather than guessing. Never "
    "invent a value you aren't reasonably confident in — a null field is "
    "expected and fine; the user reviews and fills in whatever's missing."
)

# Feature 005 US4: a hand-written schema, not one derived automatically from
# `ExtractedAttributes` via `with_structured_output(ExtractedAttributes)`.
# `ExtractedAttributes` is all-`Optional` fields (by design — a failed field
# must not block the others), which Pydantic's generated JSON schema omits
# from `required`. The gateway's structured-output mode rejects that
# ("'required' ... including every key in properties. Missing 'category'.")
# — confirmed by reproducing the real `BadRequestError`, and `strict=False`
# does not change this behavior (also reproduced). OpenAI-style structured
# outputs instead expect every property listed in `required`, with
# optionality expressed as a nullable type — so every field here is
# `["<type>", "null"]`, all fields are in `required`. The plain
# `json_object` response-format mode (no schema at all) was tried too and
# is rejected outright by this gateway route regardless of prompt content
# — this is the only mode that works against it for a schema this shape.
_EXTRACTION_SCHEMA = {
    "title": "ExtractedAttributes",
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
    },
    "required": ["category", "colors", "fabric", "warmth", "formality", "season", "pattern", "fit"],
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
        {"type": "text", "text": "Extract this item's attributes."},
        _image_content_block(image_bytes, mime_type),
    ]


@traceable(name="vision.extract_attributes", run_type="chain")
def extract_attributes_from_image(image_bytes: bytes, mime_type: str) -> ExtractedAttributes:
    """One VLM call. Raises on a genuine call failure (network/gateway error)
    — the caller (api.py) maps that to extraction_ok=False, never a 5xx, per
    FR-006.

    Uses `_EXTRACTION_SCHEMA` (a hand-written nullable-required schema, see
    its docstring) rather than deriving the schema from `ExtractedAttributes`
    directly — passing a raw dict schema makes `with_structured_output`
    return a plain dict (`JsonOutputParser`, not `PydanticOutputParser`),
    parsed into `ExtractedAttributes` here instead."""
    llm = get_chat_model(model=VISION_MODEL, temperature=0.0).with_structured_output(
        _EXTRACTION_SCHEMA, method="json_schema"
    )
    human = _build_human_message(image_bytes, mime_type)
    raw = llm.invoke([("system", SYSTEM_PROMPT), ("human", human)])
    return ExtractedAttributes(**raw)
