"""Integration tests for POST /wardrobe/items/extract and
POST /wardrobe/items/upload (Feature 003: mvp-app, US2).

vision.extract_attributes_from_image and storage.upload_wardrobe_photo are
mocked (no live gateway/Storage call, no network) -- this is about the two
new endpoints' contract and persistence, not extraction quality (that's the
golden-vision-case check, whattowear.eval.vision_harness) or a live upload.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from whattowear.api import app
from whattowear.auth import get_bearer_token, get_current_user_id
from whattowear.db import get_session
from whattowear.schema import ExtractedAttributes


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_session] = lambda: (yield db_session)
    yield TestClient(app), db_session
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(get_bearer_token, None)


def _as_user(user_id) -> None:
    app.dependency_overrides[get_current_user_id] = lambda: str(user_id)
    app.dependency_overrides[get_bearer_token] = lambda: "fake-jwt"


def test_extract_returns_unsaved_draft(client, mocker):
    c, _ = client
    _as_user(uuid.uuid4())
    mocker.patch("whattowear.api.storage.upload_wardrobe_photo", return_value="user/abc-shirt.jpg")
    mocker.patch(
        "whattowear.api.vision.extract_attributes_from_image",
        return_value=ExtractedAttributes(
            category="top", colors=["#1b2a4a"], warmth=2, formality="smart_casual", season=["spring"]
        ),
    )

    r = c.post("/wardrobe/items/extract", files={"photo": ("shirt.jpg", b"fake-bytes", "image/jpeg")})

    assert r.status_code == 200
    body = r.json()
    assert body["photo_path"] == "user/abc-shirt.jpg"
    assert body["extraction_ok"] is True
    assert body["extracted"]["category"] == "top"


def test_extract_unusable_photo_returns_200_not_error(client, mocker):
    c, _ = client
    _as_user(uuid.uuid4())
    mocker.patch("whattowear.api.storage.upload_wardrobe_photo", return_value="user/abc-blurry.jpg")
    mocker.patch("whattowear.api.vision.extract_attributes_from_image", side_effect=RuntimeError("gateway error"))

    r = c.post("/wardrobe/items/extract", files={"photo": ("blurry.jpg", b"fake-bytes", "image/jpeg")})

    assert r.status_code == 200
    body = r.json()
    assert body["extraction_ok"] is False
    assert body["extracted"]["category"] is None
    # the photo still uploaded -- the user can proceed to manual entry
    # without re-uploading (FR-006)
    assert body["photo_path"] == "user/abc-blurry.jpg"


def test_extract_requires_auth(client):
    c, _ = client
    r = c.post("/wardrobe/items/extract", files={"photo": ("shirt.jpg", b"fake-bytes", "image/jpeg")})
    assert r.status_code == 401


def _upload_payload(**overrides) -> dict:
    payload = dict(
        photo_path="user/abc-shirt.jpg",
        category="top",
        colors=["#1b2a4a"],
        formality="smart_casual",
        warmth=2,
        season=["spring"],
        fabric="cotton",
        pattern="solid",
        fit="regular",
    )
    payload.update(overrides)
    return payload


def test_upload_saves_corrected_attributes(client):
    c, _ = client
    _as_user(uuid.uuid4())

    r = c.post("/wardrobe/items/upload", json=_upload_payload(category="outerwear"))

    assert r.status_code == 201
    body = r.json()
    assert body["category"] == "outerwear"
    assert body["source"] == "upload"
    assert body["pattern"] == "solid"
    assert body["fit"] == "regular"

    closet = c.get("/wardrobe/items").json()
    assert len(closet) == 1
    assert closet[0]["category"] == "outerwear"


def test_upload_rejects_missing_pattern(client):
    c, _ = client
    _as_user(uuid.uuid4())
    payload = _upload_payload()
    del payload["pattern"]

    r = c.post("/wardrobe/items/upload", json=payload)

    assert r.status_code == 422


def test_upload_requires_auth(client):
    c, _ = client
    r = c.post("/wardrobe/items/upload", json=_upload_payload())
    assert r.status_code == 401


def test_upload_cross_user_isolation(client, mocker):
    c, _ = client
    user_a, user_b = uuid.uuid4(), uuid.uuid4()

    _as_user(user_a)
    c.post("/wardrobe/items/upload", json=_upload_payload())

    _as_user(user_b)
    closet_b = c.get("/wardrobe/items").json()

    assert closet_b == []
