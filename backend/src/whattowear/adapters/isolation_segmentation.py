"""Segmentation isolation strategy — feature 018 (photo-to-items).

A plain `requests`-based hosted background-removal call, same idiom as
`adapters/storage.py` (no SDK, no heavy client). `WTW_SEGMENTATION_API_URL`/
`WTW_SEGMENTATION_API_KEY` are unset until a real provider is chosen and an
account provisioned (specs/018-photo-to-items/research.md §5's "open
item") — this module is written against a generic "send an image + region,
get a cutout" contract so any hosted background-removal provider fits;
adjust the request/response shape below to the real provider's actual API
once one is chosen. CI never calls this live (Quality Bar); unit tests
mock the HTTP call (`tests/unit/test_isolation.py`).
"""

from __future__ import annotations

import base64
import logging
import time

import requests

from ..core.config import get_settings
from ..schema import BoundingBox, IsolationOutcome

logger = logging.getLogger(__name__)


class SegmentationIsolationClient:
    """Structurally satisfies `ports.IsolationClient`. Never raises on a
    call/timeout failure — always returns an `IsolationOutcome` with
    `image_bytes=None` instead (mirrors `adapters/storage.py::
    create_signed_url`'s fail-soft pattern), so the caller can handle every
    strategy's failure the same way (spec.md FR-013)."""

    def isolate(self, image_bytes: bytes, mime_type: str, region: BoundingBox) -> IsolationOutcome:
        settings = get_settings()
        if not settings.wtw_segmentation_api_url:
            logger.warning("WTW_SEGMENTATION_API_URL is not configured; segmentation isolation unavailable")
            return IsolationOutcome(image_bytes=None, mime_type=None, latency_seconds=0.0)

        start = time.monotonic()
        try:
            resp = requests.post(
                settings.wtw_segmentation_api_url,
                headers=(
                    {"Authorization": f"Bearer {settings.wtw_segmentation_api_key}"}
                    if settings.wtw_segmentation_api_key
                    else {}
                ),
                files={"image": ("photo", image_bytes, mime_type)},
                data={
                    "region_x": region.x,
                    "region_y": region.y,
                    "region_width": region.width,
                    "region_height": region.height,
                },
                timeout=settings.wtw_isolation_timeout_seconds,
            )
            resp.raise_for_status()
            body = resp.json()
        except requests.RequestException:
            logger.warning("Segmentation call failed; caller falls back to the region-cropped original", exc_info=True)
            return IsolationOutcome(image_bytes=None, mime_type=None, latency_seconds=time.monotonic() - start)

        elapsed = time.monotonic() - start
        image_b64 = body.get("image_base64")
        if not image_b64:
            logger.warning("Segmentation call succeeded but returned no image; treated as a failure")
            return IsolationOutcome(
                image_bytes=None,
                mime_type=None,
                mask_area_fraction=body.get("mask_area_fraction"),
                cost_usd=body.get("cost_usd"),
                latency_seconds=elapsed,
            )
        return IsolationOutcome(
            image_bytes=base64.b64decode(image_b64),
            mime_type=body.get("mime_type", "image/png"),
            mask_area_fraction=body.get("mask_area_fraction"),
            cost_usd=body.get("cost_usd"),
            latency_seconds=elapsed,
        )
