"""Closet read routes (GET, feature 004, specs/004-closet-read/contracts/
closet.md) and write routes (PATCH/favorite/wear/DELETE, feature 005,
specs/005-closet-write/contracts/closet-write.md).

Ownership is enforced twice, independently, on every route: the repository's
`WHERE user_id = ...` (the actual guarantee for this backend's own traffic —
see specs/004-closet-read/research.md §1) and the RLS policy on
`wardrobe_items`/`item_wears` (the convention, proven independent of this
backend's own connection). Category filtering and pagination happen here, in
Python, over the full list `list_wardrobe_items` returns — `ports.
ClosetRepository`'s signature takes no page/limit parameters and stays
exactly as feature 007 defined it (research.md §5); the AI pipeline's own
callers need the full wardrobe every time, so a paginated repository method
would silently break them if ever reused there. The four write routes are
all extra methods on `SupabaseClosetRepository`, not on the Protocol, for
the same reason (specs/005-closet-write/research.md §5).
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from whattowear.adapters import storage
from whattowear.auth import get_current_access_token, get_current_user_id
from whattowear.categories import CategoryGroup, group_of
from whattowear.colors import is_hex, name_to_hex, nearest_names, normalize_hex
from whattowear.core.config import get_settings
from whattowear.repositories.supabase_closet import SupabaseClosetRepository
from whattowear.schema import (
    CreateWardrobeItemFromUploadRequest,
    ExtractedAttributes,
    PhotoExtractionResponse,
    WardrobeItem,
    WardrobeItemPatch,
)
from whattowear.vision import extract_attributes_from_image

router = APIRouter()

_SUPPORTED_UPLOAD_TYPES = {"image/jpeg", "image/png", "image/webp"}

# The Closet screen's five filter chips — a strict subset of CategoryGroup's
# six taxonomy values. `full_body` has no chip of its own, so it filters
# under Bottoms (resolved in /speckit-clarify 2026-07-31, data-model.md
# "Category-group derivation") — accepting it as a query value directly
# would bypass that mapping, so the query param's type is this narrower
# Literal, not CategoryGroup itself.
ClosetChipFilter = Literal["top", "bottom", "outerwear", "footwear", "accessory"]

_CHIP_GROUP_TO_TAXONOMY_GROUPS: dict[ClosetChipFilter, tuple[CategoryGroup, ...]] = {
    "top": ("top",),
    "bottom": ("bottom", "full_body"),
    "outerwear": ("outerwear",),
    "footwear": ("footwear",),
    "accessory": ("accessory",),
}


class ClosetItemView(WardrobeItem):
    """`WardrobeItem` plus display-only computed fields the frontend must
    never re-derive itself (caught in `/speckit-analyze`): `category_group`
    (`categories.group_of`) and `color_names` (`colors.nearest_names`) are
    both backend-only Python logic. Route-local, not part of the AI-pipeline
    contract — matches `whoami.py`'s existing pattern of defining its own
    response model beside the route.

    `photo_url` (feature 006) is a short-lived signed URL minted at read
    time, never stored (data-model.md §5) — `None` when the item has no
    photo. Populated by the route, not this classmethod, since signing
    needs the caller's own access token, which this model has no access to
    and shouldn't (`ports.ClosetRepository` stays untouched)."""

    category_group: CategoryGroup
    color_names: list[str]
    photo_url: str | None = None

    @classmethod
    def from_wardrobe_item(cls, item: WardrobeItem, photo_url: str | None = None) -> ClosetItemView:
        return cls(
            **item.model_dump(),
            category_group=group_of(item.category),
            color_names=nearest_names(item.colors),
            photo_url=photo_url,
        )


class ClosetItemsResponse(BaseModel):
    items: list[ClosetItemView]
    total: int
    has_more: bool


def _get_repository() -> SupabaseClosetRepository:
    return SupabaseClosetRepository()


def _parse_item_id(item_id: str) -> None:
    """Raises the same 404 the existing GET route uses for a syntactically
    invalid id — never reaching the database's `uuid` column comparison,
    which would otherwise raise a raw, unhandled `DataError` (004's own
    fix, repeated here for every write route)."""
    try:
        uuid.UUID(item_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found") from None


def _parse_colors_text(text: str) -> list[str]:
    """Splits the edit form's single Colour text field (a comma-separated
    list of color names or hex codes) into the hex list `WardrobeItemPatch.
    colors` requires. `colors.py` draws the hex-is-truth line; this is the
    one place a UI-facing name is translated across it (data-model.md §
    "API-facing shapes"). Raises `ValueError` naming the first unrecognized
    token — never silently drops or guesses one."""
    hexes: list[str] = []
    for token in text.split(","):
        value = token.strip()
        if not value:
            continue
        if is_hex(value):
            hexes.append(normalize_hex(value))
            continue
        try:
            hexes.append(name_to_hex(value))
        except KeyError:
            raise ValueError(f"{value!r} isn't a recognized color name or hex code") from None
    return hexes


class ClosetItemEditRequest(BaseModel):
    """Route-local edit-form body — deliberately not `WardrobeItemPatch`
    itself. Every field optional (partial update); `colors_text` is the
    one bridge `WardrobeItemPatch` doesn't need, since it stays hex-only
    (research.md §4/§ "API-facing shapes"). `category` covers both the
    read view's "Category" (group) and "Group" (specific type) rows — both
    write the same underlying column, see research.md §4."""

    name: str | None = None
    category: str | None = None
    fabric: str | None = None
    colors_text: str | None = None
    notes: str | None = None


class FavoriteToggleResponse(BaseModel):
    favorite: bool


@router.get("/closet/items")
def list_closet_items(
    category: ClosetChipFilter | None = Query(default=None),  # noqa: B008
    offset: int = Query(default=0, ge=0),  # noqa: B008
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    access_token: str = Depends(get_current_access_token),  # noqa: B008
    repository: SupabaseClosetRepository = Depends(_get_repository),  # noqa: B008
) -> ClosetItemsResponse:
    items = repository.list_wardrobe_items(user_id)
    if category is not None:
        allowed_groups = _CHIP_GROUP_TO_TAXONOMY_GROUPS[category]
        items = [item for item in items if group_of(item.category) in allowed_groups]

    total = len(items)
    page_size = get_settings().wtw_closet_page_size
    page = items[offset : offset + page_size]
    has_more = offset + page_size < total

    # One batched sign call for the whole page rather than N sequential ones
    # (research.md §2 addendum).
    photo_paths = [item.photo_path for item in page if item.photo_path is not None]
    signed_urls = storage.create_signed_urls(access_token, photo_paths)

    return ClosetItemsResponse(
        items=[
            ClosetItemView.from_wardrobe_item(item, photo_url=signed_urls.get(item.photo_path or "")) for item in page
        ],
        total=total,
        has_more=has_more,
    )


@router.get("/closet/items/{item_id}")
def get_closet_item(
    item_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    access_token: str = Depends(get_current_access_token),  # noqa: B008
    repository: SupabaseClosetRepository = Depends(_get_repository),  # noqa: B008
) -> ClosetItemView:
    # A syntactically invalid id can never match a row — treated identically
    # to "doesn't exist" (spec.md's URL-tampering edge case) rather than
    # reaching the database, where the `uuid` column comparison would
    # otherwise raise a raw DataError (caught in review: a malformed id
    # crashed with an unhandled 500 instead of the same 404 every other
    # not-found case gets). Same helper every write route below reuses.
    _parse_item_id(item_id)

    item = repository.get_wardrobe_item(user_id, item_id)
    if item is None:
        # Identical shape whether item_id doesn't exist or belongs to
        # another user — never reveals which (contracts/closet.md).
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    photo_url = storage.create_signed_url(access_token, item.photo_path) if item.photo_path else None
    return ClosetItemView.from_wardrobe_item(item, photo_url=photo_url)


@router.patch("/closet/items/{item_id}")
def update_closet_item(
    item_id: str,
    body: ClosetItemEditRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseClosetRepository = Depends(_get_repository),  # noqa: B008
) -> ClosetItemView:
    _parse_item_id(item_id)

    fields = body.model_dump(exclude_unset=True, exclude={"colors_text"})
    if "colors_text" in body.model_fields_set:
        colors_text = body.colors_text
        if colors_text is not None:
            try:
                fields["colors"] = _parse_colors_text(colors_text)
            except ValueError as e:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
        else:
            fields["colors"] = None

    patch = WardrobeItemPatch(**fields)
    item = repository.update_wardrobe_item(user_id, item_id, patch)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return ClosetItemView.from_wardrobe_item(item)


@router.post("/closet/items/{item_id}/favorite")
def toggle_closet_item_favorite(
    item_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseClosetRepository = Depends(_get_repository),  # noqa: B008
) -> FavoriteToggleResponse:
    _parse_item_id(item_id)

    favorite = repository.toggle_favorite(user_id, item_id)
    if favorite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return FavoriteToggleResponse(favorite=favorite)


@router.post("/closet/items/{item_id}/wear", status_code=status.HTTP_204_NO_CONTENT)
def log_closet_item_worn(
    item_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseClosetRepository = Depends(_get_repository),  # noqa: B008
) -> None:
    _parse_item_id(item_id)

    if not repository.record_wear(user_id, item_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")


@router.delete("/closet/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_closet_item(
    item_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseClosetRepository = Depends(_get_repository),  # noqa: B008
) -> None:
    _parse_item_id(item_id)

    if not repository.delete_wardrobe_item(user_id, item_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")


# --- feature 006: photo upload + vision -------------------------------------


@router.post("/closet/items/extract")
def extract_closet_item(
    photo: UploadFile = File(...),  # noqa: B008
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    access_token: str = Depends(get_current_access_token),  # noqa: B008
) -> PhotoExtractionResponse:
    """Draft extraction only — persists nothing to `wardrobe_items`
    (contracts/wardrobe-items-extract.md). Extraction failure is always a
    200 with `extraction_ok: false`; only a genuine Storage failure 5xxs
    (handoff §5.2)."""
    if photo.content_type not in _SUPPORTED_UPLOAD_TYPES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unsupported image type")

    max_bytes = get_settings().wtw_max_upload_bytes
    file_bytes = photo.file.read(max_bytes + 1)
    if len(file_bytes) > max_bytes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "File exceeds the maximum upload size")
    if not file_bytes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Empty file")

    # A genuine Storage failure propagates as an unhandled requests.HTTPError
    # -> FastAPI's default 500 — the one case that legitimately 5xxs here.
    photo_path = storage.upload_photo(access_token, user_id, file_bytes, photo.filename or "photo", photo.content_type)

    try:
        extracted = extract_attributes_from_image(file_bytes, photo.content_type)
        extraction_ok = True
    except Exception:
        # Extraction failure (blurry photo, no garment, VLM/gateway error) is
        # never a 5xx — the photo is already uploaded, so the user can
        # proceed to manual entry without re-uploading.
        extracted = ExtractedAttributes()
        extraction_ok = False

    return PhotoExtractionResponse(photo_path=photo_path, extracted=extracted, extraction_ok=extraction_ok)


@router.post("/closet/items/from-upload", status_code=status.HTTP_201_CREATED)
def create_closet_item_from_upload(
    body: CreateWardrobeItemFromUploadRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    access_token: str = Depends(get_current_access_token),  # noqa: B008
    repository: SupabaseClosetRepository = Depends(_get_repository),  # noqa: B008
) -> ClosetItemView:
    """Creates a `wardrobe_items` row from a previously-extracted (and
    possibly corrected) draft (contracts/wardrobe-items-create-from-upload.md).
    `ports.ClosetRepository` is unchanged — this calls a repository method
    beyond the Protocol, same pattern 005's four write methods already
    established (handoff trap 5)."""
    if not body.photo_path.startswith(f"{user_id}/"):
        # The caller's own extract call always produces a path under their
        # own prefix (adapters.storage.upload_photo) — the same prefix
        # Storage RLS matches on. A path outside it can never be this
        # user's own photo.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "photo_path does not belong to this user")

    item = repository.create_wardrobe_item_from_upload(user_id, body)
    photo_url = storage.create_signed_url(access_token, item.photo_path) if item.photo_path else None
    return ClosetItemView.from_wardrobe_item(item, photo_url=photo_url)
