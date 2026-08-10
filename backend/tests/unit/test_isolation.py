"""Unit tests for feature 018's isolation strategies (specs/018-photo-to-
items/research.md §5/§6). Every adapter's HTTP/gateway call is mocked — no
live network, matching this project's Quality Bar (CI must not make live
LLM calls) and `test_vision.py`'s own pattern.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from whattowear.adapters import isolation, isolation_generative, isolation_hybrid, isolation_segmentation
from whattowear.core.config import get_settings
from whattowear.schema import BoundingBox, IsolationOutcome

REGION = BoundingBox(x=0, y=0, width=0.5, height=0.5)


class TestSegmentationIsolationClient:
    def test_returns_null_outcome_when_unconfigured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("WTW_SEGMENTATION_API_URL", raising=False)
        get_settings.cache_clear()
        client = isolation_segmentation.SegmentationIsolationClient()

        outcome = client.isolate(b"fake-bytes", "image/jpeg", REGION)

        assert outcome.image_bytes is None
        get_settings.cache_clear()

    def test_success_decodes_the_returned_image(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import base64

        monkeypatch.setenv("WTW_SEGMENTATION_API_URL", "https://segment.example/api")
        get_settings.cache_clear()
        fake_response = MagicMock()
        fake_response.json.return_value = {
            "image_base64": base64.b64encode(b"cutout-bytes").decode("ascii"),
            "mime_type": "image/png",
            "mask_area_fraction": 0.4,
            "cost_usd": 0.001,
        }
        fake_response.raise_for_status.return_value = None

        with patch.object(isolation_segmentation.requests, "post", return_value=fake_response) as mock_post:
            client = isolation_segmentation.SegmentationIsolationClient()
            outcome = client.isolate(b"fake-bytes", "image/jpeg", REGION)

        assert outcome.image_bytes == b"cutout-bytes"
        assert outcome.mime_type == "image/png"
        assert outcome.mask_area_fraction == 0.4
        mock_post.assert_called_once()
        get_settings.cache_clear()

    def test_call_failure_never_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Never raises for an ordinary call/timeout failure — returns a
        null outcome instead (ports.IsolationClient's own contract)."""
        monkeypatch.setenv("WTW_SEGMENTATION_API_URL", "https://segment.example/api")
        get_settings.cache_clear()

        with patch.object(isolation_segmentation.requests, "post", side_effect=requests.ConnectionError("boom")):
            client = isolation_segmentation.SegmentationIsolationClient()
            outcome = client.isolate(b"fake-bytes", "image/jpeg", REGION)

        assert outcome.image_bytes is None
        assert outcome.latency_seconds >= 0
        get_settings.cache_clear()


class TestGenerativeIsolationClient:
    def test_success_returns_the_edited_image(self) -> None:
        with patch.object(isolation_generative, "edit_image", return_value=b"generated-bytes") as mock_edit:
            client = isolation_generative.GenerativeIsolationClient()
            outcome = client.isolate(b"fake-bytes", "image/jpeg", REGION)

        assert outcome.image_bytes == b"generated-bytes"
        assert outcome.mime_type == "image/png"
        mock_edit.assert_called_once()

    def test_call_failure_never_raises(self) -> None:
        with patch.object(isolation_generative, "edit_image", side_effect=RuntimeError("gateway down")):
            client = isolation_generative.GenerativeIsolationClient()
            outcome = client.isolate(b"fake-bytes", "image/jpeg", REGION)

        assert outcome.image_bytes is None


class TestHybridIsolationClient:
    def _client(
        self, segmentation_outcome: IsolationOutcome, generative_outcome: IsolationOutcome | None = None
    ) -> tuple[isolation_hybrid.HybridIsolationClient, tuple[MagicMock, MagicMock]]:
        fake_segmentation = MagicMock()
        fake_segmentation.isolate.return_value = segmentation_outcome
        fake_generative = MagicMock()
        fake_generative.isolate.return_value = generative_outcome or IsolationOutcome(
            image_bytes=b"generated", mime_type="image/png", latency_seconds=1.0
        )
        return isolation_hybrid.HybridIsolationClient(segmentation=fake_segmentation, generative=fake_generative), (
            fake_segmentation,
            fake_generative,
        )

    def test_uses_segmentation_when_mask_area_is_plausible(self) -> None:
        good = IsolationOutcome(
            image_bytes=b"cutout", mime_type="image/png", mask_area_fraction=0.4, latency_seconds=1.0
        )
        client, (fake_segmentation, fake_generative) = self._client(good)

        outcome = client.isolate(b"fake-bytes", "image/jpeg", REGION)

        assert outcome.image_bytes == b"cutout"
        fake_generative.isolate.assert_not_called()

    def test_escalates_when_mask_area_is_implausibly_small(self) -> None:
        degenerate = IsolationOutcome(
            image_bytes=b"cutout", mime_type="image/png", mask_area_fraction=0.01, latency_seconds=1.0
        )
        client, (fake_segmentation, fake_generative) = self._client(degenerate)

        outcome = client.isolate(b"fake-bytes", "image/jpeg", REGION)

        fake_generative.isolate.assert_called_once()
        assert outcome.image_bytes == b"generated"

    def test_escalates_when_mask_area_is_implausibly_large(self) -> None:
        degenerate = IsolationOutcome(
            image_bytes=b"cutout", mime_type="image/png", mask_area_fraction=0.99, latency_seconds=1.0
        )
        client, (fake_segmentation, fake_generative) = self._client(degenerate)

        client.isolate(b"fake-bytes", "image/jpeg", REGION)

        fake_generative.isolate.assert_called_once()

    def test_escalates_when_segmentation_itself_failed(self) -> None:
        failed = IsolationOutcome(image_bytes=None, mime_type=None, latency_seconds=0.5)
        client, (fake_segmentation, fake_generative) = self._client(failed)

        client.isolate(b"fake-bytes", "image/jpeg", REGION)

        fake_generative.isolate.assert_called_once()

    def test_combined_latency_includes_both_calls_on_escalation(self) -> None:
        failed = IsolationOutcome(image_bytes=None, mime_type=None, latency_seconds=0.5)
        client, _ = self._client(failed, IsolationOutcome(image_bytes=b"g", mime_type="image/png", latency_seconds=1.5))

        outcome = client.isolate(b"fake-bytes", "image/jpeg", REGION)

        assert outcome.latency_seconds == pytest.approx(2.0)


class TestGetIsolationClient:
    def test_default_reads_configured_strategy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WTW_ISOLATION_STRATEGY", "generative")
        get_settings.cache_clear()

        client = isolation.get_isolation_client()

        assert isinstance(client, isolation_generative.GenerativeIsolationClient)
        get_settings.cache_clear()

    def test_explicit_override_ignores_configured_strategy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WTW_ISOLATION_STRATEGY", "segmentation")
        get_settings.cache_clear()

        client = isolation.get_isolation_client("hybrid")

        assert isinstance(client, isolation_hybrid.HybridIsolationClient)
        get_settings.cache_clear()

    def test_unknown_strategy_raises_a_clear_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown wtw_isolation_strategy"):
            isolation.get_isolation_client("not-a-real-strategy")
