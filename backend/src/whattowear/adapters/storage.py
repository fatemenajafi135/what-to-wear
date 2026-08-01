"""Supabase Storage upload and signed-URL adapter for wardrobe item photos.

Ported (not copied — handoff §3.1) from
`../app-legacy/backend/src/whattowear/storage.py`. Two things it got right,
kept unchanged: uploads use the CALLER'S OWN bearer token, never a
service-role key (Storage's per-`{user_id}` RLS policy is what enforces
isolation, not application code — specs/006-photo-upload-vision/research.md
§2); the object path is `{user_id}/{uuid4}-{filename}`, the prefix Storage's
RLS policy matches on. One thing it got wrong for this codebase: it read
`os.environ` at module scope behind `load_dotenv()`, which breaks the
zero-env import contract `test_import_safety.py` exists to catch — every
setting here is read via `get_settings()` inside each function body instead.

`create_signed_url`/`create_signed_urls` are new (the legacy prototype
never rendered real photos, so it never needed to read one back) — the
bucket is private, so every read goes through a short-lived signed URL
minted at request time, never stored (research.md §2).
"""

from __future__ import annotations

import uuid

import requests

from ..core.config import get_settings

BUCKET = "wardrobe-photos"


def _storage_base_url() -> str:
    supabase_url = get_settings().supabase_url
    return f"{supabase_url}/storage/v1"


def upload_photo(access_token: str, user_id: str, file_bytes: bytes, filename: str, content_type: str) -> str:
    """Uploads to `{BUCKET}/{user_id}/{uuid4}-{filename}` and returns that
    object path. Raises `requests.HTTPError` on a genuine upload failure —
    the one case that legitimately 5xxs on the extract route, distinct from
    an extraction failure, which is always a 200
    (contracts/wardrobe-items-extract.md)."""
    object_path = f"{user_id}/{uuid.uuid4()}-{filename}"
    resp = requests.post(
        f"{_storage_base_url()}/object/{BUCKET}/{object_path}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": content_type,
        },
        data=file_bytes,
        timeout=30,
    )
    resp.raise_for_status()
    return object_path


def create_signed_url(access_token: str, photo_path: str, expires_in: int | None = None) -> str:
    """Signs one object path. `expires_in` defaults to
    `Settings.wtw_photo_signed_url_ttl_seconds` (research.md §2)."""
    ttl = expires_in if expires_in is not None else get_settings().wtw_photo_signed_url_ttl_seconds
    resp = requests.post(
        f"{_storage_base_url()}/object/sign/{BUCKET}/{photo_path}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"expiresIn": ttl},
        timeout=10,
    )
    resp.raise_for_status()
    signed_path = resp.json()["signedURL"]
    return f"{get_settings().supabase_url}/storage/v1{signed_path}"


def create_signed_urls(access_token: str, photo_paths: list[str], expires_in: int | None = None) -> dict[str, str]:
    """Batch-signs several object paths in one HTTP call instead of N
    sequential ones — `list_closet_items` needs up to `wtw_closet_page_size`
    signed URLs per request (research.md §2 addendum). Returns
    `{photo_path: signed_url}`; an empty input returns an empty dict without
    a network call."""
    if not photo_paths:
        return {}
    ttl = expires_in if expires_in is not None else get_settings().wtw_photo_signed_url_ttl_seconds
    resp = requests.post(
        f"{_storage_base_url()}/object/sign/{BUCKET}",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"paths": photo_paths, "expiresIn": ttl},
        timeout=15,
    )
    resp.raise_for_status()
    base = f"{get_settings().supabase_url}/storage/v1"
    return {entry["path"]: f"{base}{entry['signedURL']}" for entry in resp.json()}
