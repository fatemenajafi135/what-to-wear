"""GET /api/v1/closet/items and GET /api/v1/closet/items/{item_id} — see
specs/004-closet-read/contracts/closet.md.

Ownership is enforced twice, independently: the repository's `WHERE user_id
= ...` (the actual guarantee for this backend's own traffic — see
specs/004-closet-read/research.md §1) and the RLS policy on `wardrobe_items`
(the convention, proven independent of this backend's own connection). Category
filtering and pagination happen here, in Python, over the full list
`list_wardrobe_items` returns — `ports.ClosetRepository`'s signature takes no
page/limit parameters and stays exactly as feature 007 defined it
(research.md §5); the AI pipeline's own callers need the full wardrobe every
time, so a paginated repository method would silently break them if ever
reused there.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from whattowear.auth import get_current_user_id
from whattowear.categories import CategoryGroup, group_of
from whattowear.colors import nearest_names
from whattowear.core.config import get_settings
from whattowear.repositories.supabase_closet import SupabaseClosetRepository
from whattowear.schema import WardrobeItem

router = APIRouter()

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
    response model beside the route."""

    category_group: CategoryGroup
    color_names: list[str]

    @classmethod
    def from_wardrobe_item(cls, item: WardrobeItem) -> ClosetItemView:
        return cls(
            **item.model_dump(),
            category_group=group_of(item.category),
            color_names=nearest_names(item.colors),
        )


class ClosetItemsResponse(BaseModel):
    items: list[ClosetItemView]
    total: int
    has_more: bool


def _get_repository() -> SupabaseClosetRepository:
    return SupabaseClosetRepository()


@router.get("/closet/items")
def list_closet_items(
    category: ClosetChipFilter | None = Query(default=None),  # noqa: B008
    offset: int = Query(default=0, ge=0),  # noqa: B008
    user_id: str = Depends(get_current_user_id),  # noqa: B008
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

    return ClosetItemsResponse(
        items=[ClosetItemView.from_wardrobe_item(item) for item in page],
        total=total,
        has_more=has_more,
    )


@router.get("/closet/items/{item_id}")
def get_closet_item(
    item_id: str,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseClosetRepository = Depends(_get_repository),  # noqa: B008
) -> ClosetItemView:
    item = repository.get_wardrobe_item(user_id, item_id)
    if item is None:
        # Identical shape whether item_id doesn't exist or belongs to
        # another user — never reveals which (contracts/closet.md).
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return ClosetItemView.from_wardrobe_item(item)
