"""Supabase Storage upload for wardrobe item photos (Feature 003: mvp-app, US2).

Uploads with the CALLER'S OWN bearer token (already verified by
`get_current_user_id`), never a service-role key — Storage's per-`{user_id}`
RLS policy (see specs/003-mvp-app/quickstart.md, one-time manual setup) is
what enforces per-user isolation, not application code. Uses the existing
`requests` dependency (already in pyproject.toml for the ingest layer) — no
new Supabase client package.
"""

from __future__ import annotations

import os
import uuid

import requests
from dotenv import load_dotenv

load_dotenv()

BUCKET = os.environ.get("WTW_WARDROBE_PHOTOS_BUCKET", "wardrobe-photos")


def _storage_base_url() -> str:
    supabase_url = os.environ.get("SUPABASE_URL", "")
    if not supabase_url:
        raise RuntimeError("SUPABASE_URL is required. Set it in .env (see .env.example).")
    return f"{supabase_url}/storage/v1"


def upload_wardrobe_photo(user_id: str, file_bytes: bytes, filename: str, content_type: str, access_token: str) -> str:
    """Uploads to `{BUCKET}/{user_id}/{uuid4}-{filename}` and returns that
    object path. Raises requests.HTTPError on a genuine upload failure
    (distinct from an extraction failure, which is always a 200 — see
    contracts/wardrobe-items-extract.md)."""
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
