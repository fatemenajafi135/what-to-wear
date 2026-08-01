"""Photo -> item attribute extraction.

One structured-output VLM call over a single item photo. Reuses the exact
`get_chat_model(...).with_structured_output(...)` pattern already used in
`pipeline/generator.py` — same gateway config layer, no second way to call
an LLM. This is a metadata-labeling task over a single photo the user
already chose, not outfit item selection (constitution Principle II is
about the latter).
"""

from __future__ import annotations

import base64
from typing import Any

from langsmith import traceable

from .adapters.llm_gateway import get_chat_model
from .core.config import get_settings
from .prompts import load_prompt
from .schema import ExtractedAttributes

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
    """One VLM call. Raises on a genuine call failure (network/gateway
    error) — the caller maps that to `extraction_ok=False`, never a 5xx.

    Uses `_EXTRACTION_SCHEMA` (a hand-written nullable-required schema, see
    its docstring) rather than deriving the schema from
    `ExtractedAttributes` directly — passing a raw dict schema makes
    `with_structured_output` return a plain dict (`JsonOutputParser`, not
    `PydanticOutputParser`), parsed into `ExtractedAttributes` here
    instead."""
    system_prompt, _version = load_prompt("vision_system")
    llm = get_chat_model(model=get_settings().vision_model, temperature=0.0).with_structured_output(
        _EXTRACTION_SCHEMA, method="json_schema"
    )
    human = _build_human_message(image_bytes, mime_type)
    raw: Any = llm.invoke([("system", system_prompt), ("human", human)])
    return ExtractedAttributes(**raw)
