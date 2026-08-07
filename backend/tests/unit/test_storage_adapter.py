"""adapters/storage.py — upload/sign request shape, all against a mocked
`requests` module. No network call, no live Supabase Storage.

The fail-soft signing tests below (`TestCreateSignedUrl`/
`TestCreateSignedUrls`'s failure classes) reproduce the exact response
shapes a live Supabase stack was confirmed to return for a missing object
(first live-stack review, defects 1/2): the single-object sign endpoint
answers `400` with a `{"statusCode": "404", ...}` body; the batch endpoint
answers `200` with a per-path `{"signedURL": null, "error": "..."}` entry.
Both must resolve to "no photo" (`None`/omitted), logged, never raised."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from whattowear.adapters import storage
from whattowear.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
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

    def test_missing_object_returns_none_not_raise(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # The exact shape a live stack returns for a missing object
        # (defect 1): HTTP 400, JSON body naming a 404-shaped error.
        _set_base_env(monkeypatch)
        import requests as real_requests

        mock_response = MagicMock(status_code=400)
        mock_response.json.return_value = {"statusCode": "404", "error": "not_found", "message": "Object not found"}
        mock_response.raise_for_status.side_effect = real_requests.HTTPError(response=mock_response)
        monkeypatch.setattr(storage.requests, "post", MagicMock(return_value=mock_response))

        with caplog.at_level(logging.WARNING):
            url = storage.create_signed_url("user-token", "user-123/missing.jpg")

        assert url is None
        assert "user-123/missing.jpg" in caplog.text

    def test_storage_unreachable_returns_none_not_raise(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _set_base_env(monkeypatch)
        import requests as real_requests

        monkeypatch.setattr(
            storage.requests, "post", MagicMock(side_effect=real_requests.ConnectionError("unreachable"))
        )

        with caplog.at_level(logging.WARNING):
            url = storage.create_signed_url("user-token", "user-123/a.jpg")

        assert url is None
        assert "user-123/a.jpg" in caplog.text


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

    def test_skips_entries_with_a_null_signed_url_not_a_literal_none_string(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        # The exact shape a live stack returns for a missing object in a
        # batch request (defect 2): still 200 overall, but the failed
        # path's own entry has signedURL: null and an error message.
        _set_base_env(monkeypatch)
        mock_response = MagicMock(status_code=200)
        mock_response.json.return_value = [
            {"path": "user-123/a.jpg", "signedURL": "/object/sign/wardrobe-photos/user-123/a.jpg?token=1"},
            {
                "path": "user-123/missing.jpg",
                "signedURL": None,
                "error": "Either the object does not exist or you do not have access to it",
            },
        ]
        monkeypatch.setattr(storage.requests, "post", MagicMock(return_value=mock_response))

        with caplog.at_level(logging.WARNING):
            result = storage.create_signed_urls("user-token", ["user-123/a.jpg", "user-123/missing.jpg"])

        assert result == {
            "user-123/a.jpg": "http://127.0.0.1:54321/storage/v1/object/sign/wardrobe-photos/user-123/a.jpg?token=1",
        }
        assert "user-123/missing.jpg" not in result
        assert "None" not in "".join(result.values())  # no ".../v1None"-shaped garbage URL
        assert "user-123/missing.jpg" in caplog.text

    def test_whole_batch_request_failure_returns_empty_dict_not_raise(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        _set_base_env(monkeypatch)
        import requests as real_requests

        monkeypatch.setattr(
            storage.requests, "post", MagicMock(side_effect=real_requests.ConnectionError("unreachable"))
        )

        with caplog.at_level(logging.WARNING):
            result = storage.create_signed_urls("user-token", ["user-123/a.jpg", "user-123/b.jpg"])

        assert result == {}
        assert "2" in caplog.text  # logs how many paths were affected
