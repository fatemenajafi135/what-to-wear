"""Unit tests for the extract route's request-validation edges
(contracts/wardrobe-items-extract.md) — no database, no network. Identity
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
    extract_mock = MagicMock()
    monkeypatch.setattr(closet_routes.storage, "upload_photo", upload_mock)
    monkeypatch.setattr(closet_routes, "extract_attributes_from_image", extract_mock)
    return upload_mock, extract_mock


def test_missing_photo_field_is_422(client: TestClient, _mock_storage_and_vision: tuple[MagicMock, MagicMock]) -> None:
    upload_mock, extract_mock = _mock_storage_and_vision
    resp = client.post("/api/v1/closet/items/extract", files={})

    assert resp.status_code == 422
    upload_mock.assert_not_called()
    extract_mock.assert_not_called()


def test_unsupported_content_type_is_422(
    client: TestClient, _mock_storage_and_vision: tuple[MagicMock, MagicMock]
) -> None:
    upload_mock, extract_mock = _mock_storage_and_vision
    resp = client.post(
        "/api/v1/closet/items/extract",
        files={"photo": ("shirt.gif", b"fake-bytes", "image/gif")},
    )

    assert resp.status_code == 422
    upload_mock.assert_not_called()
    extract_mock.assert_not_called()


def test_oversized_file_is_422(
    client: TestClient, _mock_storage_and_vision: tuple[MagicMock, MagicMock], monkeypatch: pytest.MonkeyPatch
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("WTW_MAX_UPLOAD_BYTES", "10")
    upload_mock, extract_mock = _mock_storage_and_vision

    resp = client.post(
        "/api/v1/closet/items/extract",
        files={"photo": ("shirt.jpg", b"x" * 100, "image/jpeg")},
    )

    assert resp.status_code == 422
    upload_mock.assert_not_called()
    extract_mock.assert_not_called()
    get_settings.cache_clear()


def test_valid_upload_calls_storage_and_vision(
    client: TestClient, _mock_storage_and_vision: tuple[MagicMock, MagicMock]
) -> None:
    from whattowear.schema import ExtractedAttributes

    upload_mock, extract_mock = _mock_storage_and_vision
    extract_mock.return_value = ExtractedAttributes(category="top")

    resp = client.post(
        "/api/v1/closet/items/extract",
        files={"photo": ("shirt.jpg", b"x" * 100, "image/jpeg")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["extraction_ok"] is True
    assert body["extracted"]["category"] == "top"
    upload_mock.assert_called_once()
    extract_mock.assert_called_once()


def test_extraction_failure_is_200_not_5xx(
    client: TestClient, _mock_storage_and_vision: tuple[MagicMock, MagicMock]
) -> None:
    upload_mock, extract_mock = _mock_storage_and_vision
    extract_mock.side_effect = RuntimeError("gateway error")

    resp = client.post(
        "/api/v1/closet/items/extract",
        files={"photo": ("shirt.jpg", b"x" * 100, "image/jpeg")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["extraction_ok"] is False
    assert body["extracted"]["category"] is None
    upload_mock.assert_called_once()
