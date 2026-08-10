"""Hybrid isolation strategy — feature 018 (photo-to-items, spec.md
FR-011/FR-012). Segments first; escalates to generative reconstruction
only when the segmentation result is degenerate, per a MEASURABLE
property of its own output (never an unspecified "when it looks bad" —
spec.md FR-012, research.md §6).
"""

from __future__ import annotations

import logging

from ..core.config import get_settings
from ..schema import BoundingBox, IsolationOutcome
from .isolation_generative import GenerativeIsolationClient
from .isolation_segmentation import SegmentationIsolationClient

logger = logging.getLogger(__name__)


class HybridIsolationClient:
    """Structurally satisfies `ports.IsolationClient`. Composes the other
    two adapters directly (plain function composition) — no third HTTP
    call of its own."""

    def __init__(
        self,
        segmentation: SegmentationIsolationClient | None = None,
        generative: GenerativeIsolationClient | None = None,
    ) -> None:
        # Injectable for tests; defaults to the real adapters otherwise.
        self._segmentation = segmentation or SegmentationIsolationClient()
        self._generative = generative or GenerativeIsolationClient()

    def isolate(self, image_bytes: bytes, mime_type: str, region: BoundingBox) -> IsolationOutcome:
        segmentation_result = self._segmentation.isolate(image_bytes, mime_type, region)

        if self._should_escalate(segmentation_result):
            logger.info(
                "Segmentation result degenerate (mask_area_fraction=%r, succeeded=%s); escalating to generative",
                segmentation_result.mask_area_fraction,
                segmentation_result.image_bytes is not None,
            )
            generative_result = self._generative.isolate(image_bytes, mime_type, region)
            # Combined latency — the hybrid's own real cost, not just the
            # winning call's (research.md §9's isolation_report() measures
            # this path's actual wall-clock time, not a lower bound).
            return generative_result.model_copy(
                update={"latency_seconds": segmentation_result.latency_seconds + generative_result.latency_seconds}
            )

        return segmentation_result

    @staticmethod
    def _should_escalate(result: IsolationOutcome) -> bool:
        """The measurable trigger FR-012 requires (research.md §6):
        segmentation failed outright, or its own reported mask area is
        implausibly small (essentially nothing isolated) or implausibly
        large (essentially nothing removed) — both explicitly PROVISIONAL
        thresholds, tuned from real eval/vision_harness.py
        --isolation-report numbers once they exist (docs/design-
        decisions.md §62)."""
        if result.image_bytes is None:
            return True
        if result.mask_area_fraction is None:
            # No mask reported at all — can't confirm the result is good,
            # so treat it the same as "degenerate" rather than trusting an
            # un-measured success.
            return True
        settings = get_settings()
        return (
            result.mask_area_fraction < settings.wtw_isolation_hybrid_min_area
            or result.mask_area_fraction > settings.wtw_isolation_hybrid_max_area
        )
