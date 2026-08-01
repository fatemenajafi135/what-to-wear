"""adapters/storage.py — upload/sign request shape, all against a mocked
`requests` module. No network call, no live Supabase Storage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from whattowear.adapters import storage
from whattowear.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set_base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")


class TestUploadPhoto:
    def test_posts_to_the_right_object_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_base_env(monkeypatch)
        mock_response = MagicMock(status_code=200)
        mock_post = MagicMock(return_value=mock_response)
        monkeypatch.setattr(storage.requests, "post", mock_post)

        path = storage.upload_photo("user-token", "user-123", b"fake-bytes", "shirt.jpg", "image/jpeg")

        assert path.startswith("user-123/")
        assert path.endswith("-shirt.jpg")
        call_url = mock_post.call_args.args[0]
        assert call_url == f"http://127.0.0.1:54321/storage/v1/object/wardrobe-photos/{path}"
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer user-token"
        assert headers["Content-Type"] == "image/jpeg"
        assert mock_post.call_args.kwargs["data"] == b"fake-bytes"

    def test_raises_on_a_genuine_upload_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_base_env(monkeypatch)
        import requests as real_requests

        mock_response = MagicMock(status_code=500)
        mock_response.raise_for_status.side_effect = real_requests.HTTPError("upstream failure")
        monkeypatch.setattr(storage.requests, "post", MagicMock(return_value=mock_response))

        with pytest.raises(real_requests.HTTPError):
            storage.upload_photo("user-token", "user-123", b"fake-bytes", "shirt.jpg", "image/jpeg")


class TestCreateSignedUrl:
    def test_returns_full_signed_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_base_env(monkeypatch)
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"signedURL": "/object/sign/wardrobe-photos/user-123/a.jpg?token=abc"}
        mock_post = MagicMock(return_value=mock_response)
        monkeypatch.setattr(storage.requests, "post", mock_post)

        url = storage.create_signed_url("user-token", "user-123/a.jpg")

        assert url == ("http://127.0.0.1:54321/storage/v1/object/sign/wardrobe-photos/user-123/a.jpg?token=abc")
        call_url = mock_post.call_args.args[0]
        assert call_url == "http://127.0.0.1:54321/storage/v1/object/sign/wardrobe-photos/user-123/a.jpg"
        assert mock_post.call_args.kwargs["json"]["expiresIn"] == 3600  # default TTL

    def test_respects_custom_ttl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_base_env(monkeypatch)
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = {"signedURL": "/object/sign/wardrobe-photos/user-123/a.jpg?token=abc"}
        mock_post = MagicMock(return_value=mock_response)
        monkeypatch.setattr(storage.requests, "post", mock_post)

        storage.create_signed_url("user-token", "user-123/a.jpg", expires_in=60)

        assert mock_post.call_args.kwargs["json"]["expiresIn"] == 60


class TestCreateSignedUrls:
    def test_empty_input_makes_no_network_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_base_env(monkeypatch)
        mock_post = MagicMock()
        monkeypatch.setattr(storage.requests, "post", mock_post)

        result = storage.create_signed_urls("user-token", [])

        assert result == {}
        mock_post.assert_not_called()

    def test_batches_multiple_paths_in_one_call(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_base_env(monkeypatch)
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = [
            {"path": "user-123/a.jpg", "signedURL": "/object/sign/wardrobe-photos/user-123/a.jpg?token=1"},
            {"path": "user-123/b.jpg", "signedURL": "/object/sign/wardrobe-photos/user-123/b.jpg?token=2"},
        ]
        mock_post = MagicMock(return_value=mock_response)
        monkeypatch.setattr(storage.requests, "post", mock_post)

        result = storage.create_signed_urls("user-token", ["user-123/a.jpg", "user-123/b.jpg"])

        assert mock_post.call_count == 1
        assert mock_post.call_args.kwargs["json"]["paths"] == ["user-123/a.jpg", "user-123/b.jpg"]
        assert result == {
            "user-123/a.jpg": "http://127.0.0.1:54321/storage/v1/object/sign/wardrobe-photos/user-123/a.jpg?token=1",
            "user-123/b.jpg": "http://127.0.0.1:54321/storage/v1/object/sign/wardrobe-photos/user-123/b.jpg?token=2",
        }
