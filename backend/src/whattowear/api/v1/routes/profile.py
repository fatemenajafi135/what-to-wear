"""Profile & Settings endpoints (feature 013).

See specs/013-profile-settings/contracts/profile-settings-api.md. Account (email) and
Connected accounts have no routes here by design — see that contract's closing sections.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from whattowear.auth import get_current_user_id
from whattowear.core.db import get_session
from whattowear.repositories import profile_repository
from whattowear.schemas.profile import (
    BodySizeUpdate,
    NotificationsUpdate,
    ProfileResponse,
    StylePreferencesUpdate,
)

router = APIRouter()


@router.get("/profile")
def get_profile(
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session),  # noqa: B008
) -> ProfileResponse:
    return profile_repository.get_or_default(session, user_id)


@router.patch("/profile/style-preferences")
def update_style_preferences(
    update: StylePreferencesUpdate,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session),  # noqa: B008
) -> ProfileResponse:
    return profile_repository.upsert_style_preferences(session, user_id, update)


@router.patch("/profile/body-size")
def update_body_size(
    update: BodySizeUpdate,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session),  # noqa: B008
) -> ProfileResponse:
    return profile_repository.upsert_body_size(session, user_id, update)


@router.patch("/profile/notifications")
def update_notifications(
    update: NotificationsUpdate,
    user_id: str = Depends(get_current_user_id),
    session: Session = Depends(get_session),  # noqa: B008
) -> ProfileResponse:
    return profile_repository.upsert_notifications(session, user_id, update)
