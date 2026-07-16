"""Integration tests for POST /wardrobe/items/{id}/photo (replace) and
PATCH /wardrobe/items/{id} with photo_path (remove) -- Feature 008 US4.

storage.upload_wardrobe_photo is mocked (no live Storage call, no network),
same pattern as test_wardrobe_photo_flow.py. vision.extract_attributes_from_image
is never called by the replace endpoint at all -- not mocked because it must
never be invoked (FR-014); no LLM calls anywhere in this file.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from whattowear import crud
from whattowear.api import app
from whattowear.auth import get_bearer_token, get_current_user_id
from whattowear.db import get_session
from whattowear.models import WardrobeItemRow


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


def _add_item(db_session, user_id: uuid.UUID, **overrides) -> WardrobeItemRow:
    defaults = dict(
        user_id=user_id,
        category="top",
        colors=["#1b2a4a"],
        formality="smart_casual",
        warmth=2,
        season=["spring"],
        fabric="cotton",
        pattern="solid",
        fit="regular",
        source="upload",
        photo_path="user/original-photo.jpg",
    )
    defaults.update(overrides)
    row = WardrobeItemRow(**defaults)
    db_session.add(row)
    db_session.commit()
    return row


def test_replace_photo_updates_path_and_leaves_other_fields_unchanged(client, mocker):
    c, db_session = client
    user_id = uuid.uuid4()
    row = _add_item(db_session, user_id)
    mocker.patch("whattowear.api.storage.upload_wardrobe_photo", return_value="user/new-photo.jpg")
    extract_mock = mocker.patch("whattowear.api.vision.extract_attributes_from_image")
    _as_user(user_id)

    r = c.post(f"/wardrobe/items/{row.id}/photo", files={"photo": ("new.jpg", b"fake-bytes", "image/jpeg")})

    assert r.status_code == 200
    body = r.json()
    assert body["photo_path"] == "user/new-photo.jpg"
    # FR-014: replacing a photo never re-classifies the item.
    assert body["category"] == "top"
    assert body["fabric"] == "cotton"
    assert body["pattern"] == "solid"
    assert body["fit"] == "regular"
    extract_mock.assert_not_called()


def test_remove_photo_via_patch_clears_it(client):
    c, db_session = client
    user_id = uuid.uuid4()
    row = _add_item(db_session, user_id)
    _as_user(user_id)

    r = c.patch(f"/wardrobe/items/{row.id}", json={"photo_path": None})

    assert r.status_code == 200
    assert r.json()["photo_path"] is None


def test_replace_photo_cross_user_returns_404(client, mocker):
    c, db_session = client
    owner, other = uuid.uuid4(), uuid.uuid4()
    row = _add_item(db_session, owner)
    mocker.patch("whattowear.api.storage.upload_wardrobe_photo", return_value="user/new-photo.jpg")
    _as_user(other)

    r = c.post(f"/wardrobe/items/{row.id}/photo", files={"photo": ("new.jpg", b"fake-bytes", "image/jpeg")})

    assert r.status_code == 404
    assert crud.list_wardrobe_items(db_session, owner)[0].photo_path == "user/original-photo.jpg"


def test_remove_photo_cross_user_returns_404(client):
    c, db_session = client
    owner, other = uuid.uuid4(), uuid.uuid4()
    row = _add_item(db_session, owner)
    _as_user(other)

    r = c.patch(f"/wardrobe/items/{row.id}", json={"photo_path": None})

    assert r.status_code == 404
    assert crud.list_wardrobe_items(db_session, owner)[0].photo_path == "user/original-photo.jpg"


def test_add_photo_to_item_with_none(client, mocker):
    c, db_session = client
    user_id = uuid.uuid4()
    row = _add_item(db_session, user_id, photo_path=None, source="catalog")
    mocker.patch("whattowear.api.storage.upload_wardrobe_photo", return_value="user/first-photo.jpg")
    _as_user(user_id)

    r = c.post(f"/wardrobe/items/{row.id}/photo", files={"photo": ("first.jpg", b"fake-bytes", "image/jpeg")})

    assert r.status_code == 200
    assert r.json()["photo_path"] == "user/first-photo.jpg"
