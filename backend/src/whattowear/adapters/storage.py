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

Both signing functions fail SOFT, on purpose (found in first live-stack
review, defects 1/2): a missing Storage object, or Storage being
temporarily unreachable, must never take down an item read — a
decorative thumbnail is not worth a 500. Verified against the live
stack: the single-object sign endpoint returns HTTP 400 with a
`{"statusCode": "404", "error": "not_found", ...}` body for a missing
object (an unhandled `raise_for_status()` there turned into a 500 on
both `GET /closet/items/{item_id}` and `POST /closet/items/from-upload`
before this fix); the *batch* sign endpoint instead returns 200 with a
per-path `{"error": "...", "signedURL": null}` entry, which an
unconditional dict comprehension turned into a literal `".../v1None"`
URL — a broken `<img>` the frontend had no way to fall back from, since
nothing signaled the failure. Both are now logged (never swallowed
silently) and resolved to `None`/omitted, which `ClosetItemView.
photo_url` and the frontend's `NoPhoto` component already treat as
"no photo" — no caller-side change needed.
"""

from __future__ import annotations

import logging
import uuid

import requests

from ..core.config import get_settings

logger = logging.getLogger(__name__)

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


def create_signed_url(access_token: str, photo_path: str, expires_in: int | None = None) -> str | None:
    """Signs one object path. `expires_in` defaults to
    `Settings.wtw_photo_signed_url_ttl_seconds` (research.md §2). Returns
    `None` — logged, not raised — on any signing failure (missing object,
    Storage unreachable, a non-2xx response): a decorative thumbnail must
    never take the item read down with it (defect 1)."""
    ttl = expires_in if expires_in is not None else get_settings().wtw_photo_signed_url_ttl_seconds
    try:
        resp = requests.post(
            f"{_storage_base_url()}/object/sign/{BUCKET}/{photo_path}",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"expiresIn": ttl},
            timeout=10,
        )
        resp.raise_for_status()
        signed_path = resp.json()["signedURL"]
    except requests.RequestException:
        logger.warning("Failed to sign photo_path=%r; rendering as no-photo", photo_path, exc_info=True)
        return None
    return f"{get_settings().supabase_url}/storage/v1{signed_path}"


def create_signed_urls(access_token: str, photo_paths: list[str], expires_in: int | None = None) -> dict[str, str]:
    """Batch-signs several object paths in one HTTP call instead of N
    sequential ones — `list_closet_items` needs up to `wtw_closet_page_size`
    signed URLs per request (research.md §2 addendum). Returns
    `{photo_path: signed_url}`, omitting any path that failed to sign
    (missing object, or an entry Storage itself reports as failed within
    an otherwise-200 batch response — defect 2) rather than building a
    broken URL from a `null` `signedURL`. An empty input, or a whole-batch
    request failure (Storage unreachable), returns an empty dict — both
    logged, neither raised, so a page's worth of items degrades to "no
    photo" per item instead of failing the whole request."""
    if not photo_paths:
        return {}
    ttl = expires_in if expires_in is not None else get_settings().wtw_photo_signed_url_ttl_seconds
    try:
        resp = requests.post(
            f"{_storage_base_url()}/object/sign/{BUCKET}",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"paths": photo_paths, "expiresIn": ttl},
            timeout=15,
        )
        resp.raise_for_status()
        entries = resp.json()
    except requests.RequestException:
        logger.warning(
            "Failed to batch-sign %d photo path(s); rendering all as no-photo", len(photo_paths), exc_info=True
        )
        return {}

    base = f"{get_settings().supabase_url}/storage/v1"
    result: dict[str, str] = {}
    for entry in entries:
        signed_path = entry.get("signedURL")
        if not signed_path:
            logger.warning(
                "Signing failed for photo_path=%r: %s; rendering as no-photo", entry.get("path"), entry.get("error")
            )
            continue
        result[entry["path"]] = f"{base}{signed_path}"
    return result
