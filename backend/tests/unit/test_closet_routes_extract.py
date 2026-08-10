"""Unit tests for the extract route's request-validation edges
(contracts/closet-items-extract.md) — no database, no network. Identity
is supplied via FastAPI dependency overrides (matches
test_closet_routes.py's own precedent); Storage and the VLM are both
monkeypatched at the route module's imported names so a 422 case never
reaches either.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from whattowear.api.v1.routes import closet as closet_routes
from whattowear.auth import get_current_access_token, get_current_user_id
from whattowear.core.config import get_settings
from whattowear.main import app

USER_A = "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[get_current_user_id] = lambda: USER_A
    app.dependency_overrides[get_current_access_token] = lambda: "fake-access-token"
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _mock_storage_and_vision(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    upload_mock = MagicMock(return_value=f"{USER_A}/fake-uuid-shirt.jpg")
    detect_mock = MagicMock()
    monkeypatch.setattr(closet_routes.storage, "upload_photo", upload_mock)
    monkeypatch.setattr(closet_routes, "detect_garments_from_image", detect_mock)
    return upload_mock, detect_mock


def test_missing_photo_field_is_422(client: TestClient, _mock_storage_and_vision: tuple[MagicMock, MagicMock]) -> None:
    upload_mock, detect_mock = _mock_storage_and_vision
    resp = client.post("/api/v1/closet/items/extract", files={})

    assert resp.status_code == 422
    upload_mock.assert_not_called()
    detect_mock.assert_not_called()


def test_unsupported_content_type_is_422(
    client: TestClient, _mock_storage_and_vision: tuple[MagicMock, MagicMock]
) -> None:
    upload_mock, detect_mock = _mock_storage_and_vision
    resp = client.post(
        "/api/v1/closet/items/extract",
        files={"photo": ("shirt.gif", b"fake-bytes", "image/gif")},
    )

    assert resp.status_code == 422
    upload_mock.assert_not_called()
    detect_mock.assert_not_called()


def test_oversized_file_is_422(
    client: TestClient, _mock_storage_and_vision: tuple[MagicMock, MagicMock], monkeypatch: pytest.MonkeyPatch
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("WTW_MAX_UPLOAD_BYTES", "10")
    upload_mock, detect_mock = _mock_storage_and_vision

    resp = client.post(
        "/api/v1/closet/items/extract",
        files={"photo": ("shirt.jpg", b"x" * 100, "image/jpeg")},
    )

    assert resp.status_code == 422
    upload_mock.assert_not_called()
    detect_mock.assert_not_called()
    get_settings.cache_clear()


def test_single_detection_returns_one_draft(
    client: TestClient, _mock_storage_and_vision: tuple[MagicMock, MagicMock]
) -> None:
    """A photo containing one garment MUST still produce exactly one draft
    in the (now always-a-list) response — spec.md FR-004."""
    from whattowear.schema import BoundingBox, DetectedGarment, ExtractedAttributes

    upload_mock, detect_mock = _mock_storage_and_vision
    detect_mock.return_value = (
        [
            DetectedGarment(
                region=BoundingBox(x=0, y=0, width=1, height=1),
                attributes=ExtractedAttributes(category="top", colors=["#1b2a4a"]),
            )
        ],
        False,
    )

    resp = client.post(
        "/api/v1/closet/items/extract",
        files={"photo": ("shirt.jpg", b"x" * 100, "image/jpeg")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["drafts"]) == 1
    draft = body["drafts"][0]
    assert draft["extraction_ok"] is True
    assert draft["extracted"]["category"] == "top"
    # Route-local computed field (research.md §5) — the review card
    # pre-fills Color with a name, not the raw hex.
    assert draft["color_names"] == ["navy"]
    assert draft["isolated_photo_path"] is None
    assert body["truncated"] is False
    upload_mock.assert_called_once()
    detect_mock.assert_called_once()


def test_multiple_detections_returns_multiple_drafts(
    client: TestClient, _mock_storage_and_vision: tuple[MagicMock, MagicMock]
) -> None:
    from whattowear.schema import BoundingBox, DetectedGarment, ExtractedAttributes

    upload_mock, detect_mock = _mock_storage_and_vision
    detect_mock.return_value = (
        [
            DetectedGarment(
                region=BoundingBox(x=0, y=0, width=0.4, height=0.6),
                attributes=ExtractedAttributes(category="t-shirt"),
            ),
            DetectedGarment(
                region=BoundingBox(x=0.5, y=0, width=0.4, height=0.6),
                attributes=ExtractedAttributes(category="jeans"),
            ),
        ],
        False,
    )

    resp = client.post(
        "/api/v1/closet/items/extract",
        files={"photo": ("flatlay.jpg", b"x" * 100, "image/jpeg")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert [d["extracted"]["category"] for d in body["drafts"]] == ["t-shirt", "jeans"]


def test_truncated_flag_passed_through(
    client: TestClient, _mock_storage_and_vision: tuple[MagicMock, MagicMock]
) -> None:
    from whattowear.schema import BoundingBox, DetectedGarment, ExtractedAttributes

    upload_mock, detect_mock = _mock_storage_and_vision
    detect_mock.return_value = (
        [DetectedGarment(region=BoundingBox(x=0, y=0, width=1, height=1), attributes=ExtractedAttributes())],
        True,
    )

    resp = client.post(
        "/api/v1/closet/items/extract",
        files={"photo": ("pile.jpg", b"x" * 100, "image/jpeg")},
    )

    assert resp.json()["truncated"] is True


def test_detection_call_failure_falls_back_to_one_blank_draft(
    client: TestClient, _mock_storage_and_vision: tuple[MagicMock, MagicMock]
) -> None:
    """A genuine call failure (network/gateway error) falls back to today's
    single-draft behavior — never zero drafts, never a 5xx (spec.md
    FR-003)."""
    upload_mock, detect_mock = _mock_storage_and_vision
    detect_mock.side_effect = RuntimeError("gateway error")

    resp = client.post(
        "/api/v1/closet/items/extract",
        files={"photo": ("shirt.jpg", b"x" * 100, "image/jpeg")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["drafts"]) == 1
    assert body["drafts"][0]["extraction_ok"] is False
    assert body["drafts"][0]["extracted"]["category"] is None
    assert body["drafts"][0]["region"] == {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}
    assert body["truncated"] is False
    upload_mock.assert_called_once()


def test_zero_confident_detections_falls_back_to_one_blank_draft(
    client: TestClient, _mock_storage_and_vision: tuple[MagicMock, MagicMock]
) -> None:
    """The call SUCCEEDING with nothing found is today's existing "nothing
    found" semantics (extraction_ok=True, all-null) — distinct from a call
    failure above (spec.md FR-003)."""
    upload_mock, detect_mock = _mock_storage_and_vision
    detect_mock.return_value = ([], False)

    resp = client.post(
        "/api/v1/closet/items/extract",
        files={"photo": ("blurry.jpg", b"x" * 100, "image/jpeg")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["drafts"]) == 1
    assert body["drafts"][0]["extraction_ok"] is True
    assert body["drafts"][0]["extracted"]["category"] is None
