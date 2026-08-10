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
from .categories import group_of
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


# Two regions overlapping this much are treated as the same garment.
#
# Deliberately high. The observed failure was near-identical full-frame boxes
# (IoU ~0.96), so 0.8 catches it comfortably. A lower bar was tried and merged
# detections overlapping ~0.6 — which in a folded stack or a rack of hangers
# can be two real garments. Losing a genuine item is worse than showing one
# duplicate the user can delete, so this errs toward keeping.
_DUPLICATE_IOU = 0.8


def _iou(a: BoundingBox, b: BoundingBox) -> float:
    """Intersection-over-union of two regions."""
    ax2, ay2 = a.x + a.width, a.y + a.height
    bx2, by2 = b.x + b.width, b.y + b.height
    ix = max(0.0, min(ax2, bx2) - max(a.x, b.x))
    iy = max(0.0, min(ay2, by2) - max(a.y, b.y))
    inter = ix * iy
    union = a.width * a.height + b.width * b.height - inter
    return inter / union if union > 0 else 0.0


def _drop_overlapping(detections: list[DetectedGarment]) -> list[DetectedGarment]:
    """Discard detections that substantially cover one already kept.

    A deliberately blunt, deterministic guard against the model returning the
    same garment more than once. It was doing exactly that on ordinary
    single-garment product shots: two near-identical full-frame regions came
    back, so one skirt became two closet items with the same photo.

    Detections arrive ordered most-confident-first (see the system prompt), so
    the first occurrence is kept and later overlapping ones dropped.

    This cannot fix every over-detection — a pair of earrings side by side, or
    a dress split into bodice and skirt, produce regions that barely overlap.
    Those are addressed in `prompts/vision_system.md`, which is the only place
    that can reason about what *is* one garment. This handles the mechanical
    duplicate case, which no prompt wording reliably prevents.
    """
    kept: list[DetectedGarment] = []
    for detection in detections:
        if any(_iou(detection.region, k.region) >= _DUPLICATE_IOU for k in kept):
            continue
        kept.append(detection)
    return kept


def _region_union(a: BoundingBox, b: BoundingBox) -> BoundingBox:
    """The smallest region containing both — used so a merged pair's crop
    shows both halves (e.g. both earrings), not just the one whose
    detection survived."""
    x1, y1 = min(a.x, b.x), min(a.y, b.y)
    x2 = max(a.x + a.width, b.x + b.width)
    y2 = max(a.y + a.height, b.y + b.height)
    return BoundingBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1)


def _pairable(a: ExtractedAttributes, b: ExtractedAttributes) -> bool:
    """Same category, same group, same colors, and no conflicting
    fabric/pattern/fit — the criteria a real pair (two earrings, two
    gloves) actually shares. Requested after `_drop_overlapping` alone left
    side-by-side pairs unmerged: their regions barely overlap, so IoU can't
    catch them.

    Category equality already implies group equality today (`group_of` is a
    pure function of category) — the group check is kept anyway as an
    explicit statement of intent, so a future change to the category list
    can't silently loosen this without someone noticing here.

    `colors` must be present and equal as sets on both sides: color is the
    one signal that reliably distinguishes "the same pair, twice" from "two
    different, unrelated items that happen to share a category" (e.g. two
    different rings). Absent color data means "can't confirm", not "assume
    a match" — no merge.

    fabric/pattern/fit only block a merge when BOTH sides extracted a value
    AND it disagrees; either side leaving a field null does not, since a
    null means "the model didn't extract this," not "this differs."
    """
    if not a.category or not b.category or a.category != b.category:
        return False
    if group_of(a.category) != group_of(b.category):
        return False
    if not a.colors or not b.colors or set(a.colors) != set(b.colors):
        return False
    for field in ("fabric", "pattern", "fit"):
        va, vb = getattr(a, field), getattr(b, field)
        if va is not None and vb is not None and va != vb:
            return False
    return True


def _merge_matching_pairs(detections: list[DetectedGarment]) -> list[DetectedGarment]:
    """Collapse a side-by-side pair (e.g. two earrings, non-overlapping
    regions) into one detection once `_pairable` confirms they agree on
    every attribute the model actually extracted.

    Merges at most two at a time, in order (each detection matches against
    at most one later one) — deliberately not a full pairwise cluster.
    `_pairable`'s per-field checks are not guaranteed transitive (A and B
    can both be null-vs-set "compatible" with C while B and C actively
    disagree on that same field), so a wider merge risks collapsing three
    genuinely different items that share a category. Two duplicate-of-a-pair
    detections is the observed failure; this fixes exactly that without
    reasoning about larger, unobserved groupings.
    """
    merged: list[DetectedGarment] = []
    consumed: set[int] = set()
    for i, detection in enumerate(detections):
        if i in consumed:
            continue
        partner = next(
            (
                j
                for j in range(i + 1, len(detections))
                if j not in consumed and _pairable(detection.attributes, detections[j].attributes)
            ),
            None,
        )
        if partner is None:
            merged.append(detection)
            continue
        consumed.add(partner)
        merged.append(
            DetectedGarment(
                region=_region_union(detection.region, detections[partner].region),
                attributes=detection.attributes,
            )
        )
    return merged


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
    detections = _drop_overlapping(detections)
    detections = _merge_matching_pairs(detections)
    max_detections = get_settings().wtw_max_detections_per_photo
    truncated = len(detections) > max_detections
    return detections[:max_detections], truncated
