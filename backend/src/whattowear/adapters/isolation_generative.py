"""Generative-reconstruction isolation strategy — feature 018
(photo-to-items). Routes through the existing AI Gateway
(`adapters.llm_gateway.edit_image`), not a second LLM client — see that
function's docstring for why it calls `litellm.image_edit` directly rather
than a `ChatLiteLLM`-style wrapper.
"""

from __future__ import annotations

import logging
import time

from ..adapters.llm_gateway import edit_image
from ..schema import BoundingBox, IsolationOutcome

logger = logging.getLogger(__name__)

_PROMPT = (
    "Produce a clean, isolated product photo of just the garment in the highlighted "
    "region of this image. Remove the background and any other garments or people. "
    "Keep the garment's true colors, pattern and shape unchanged."
)


class GenerativeIsolationClient:
    """Structurally satisfies `ports.IsolationClient`. Same fail-soft
    contract as `SegmentationIsolationClient` — never raises, returns
    `image_bytes=None` on any failure (spec.md FR-013)."""

    def isolate(self, image_bytes: bytes, mime_type: str, region: BoundingBox) -> IsolationOutcome:
        start = time.monotonic()
        region_desc = f"x={region.x:.2f}, y={region.y:.2f}, width={region.width:.2f}, height={region.height:.2f}"
        prompt = f"{_PROMPT} Region: {region_desc}."
        try:
            result_bytes = edit_image(image_bytes, mime_type, prompt)
        except Exception:
            logger.warning(
                "Generative isolation call failed; caller falls back to the region-cropped original", exc_info=True
            )
            return IsolationOutcome(image_bytes=None, mime_type=None, latency_seconds=time.monotonic() - start)

        return IsolationOutcome(
            image_bytes=result_bytes,
            mime_type="image/png",
            # No mask — this strategy has nothing analogous to segmentation's
            # area fraction, and never itself triggers the hybrid escalation
            # (adapters/isolation_hybrid.py calls IN to this strategy, never
            # the reverse).
            mask_area_fraction=None,
            # litellm's ImageResponse doesn't currently surface a per-call
            # cost for image-edit the way token-usage-based cost tracking
            # does for chat — left None until a real measurement (research.md
            # §9's isolation_report()) shows what's actually available.
            cost_usd=None,
            latency_seconds=time.monotonic() - start,
        )
