"""All database access for the `user_profile` table.

Raw parameterized SQL via `sqlalchemy.text()` against `get_session()` — this codebase has no
SQLAlchemy ORM/declarative layer anywhere yet (see plan.md's Project Structure note); this
repository doesn't introduce one for a single table.

Every function is scoped by `user_id` (the JWT-verified caller, injected by the route layer's
`get_current_user_id` dependency) — this is what actually enforces per-user isolation through
this backend's own Postgres connection, since that connection's role bypasses RLS (see
specs/013-profile-settings/research.md §1). The RLS policy on this table is proven separately,
by `tests/integration/test_user_profile_rls.py`.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from whattowear.schemas.profile import (
    BodySizeUpdate,
    NotificationsUpdate,
    ProfileResponse,
    StylePreferencesUpdate,
)


def _row_to_response(row: Any) -> ProfileResponse:
    return ProfileResponse(
        style_tags=list(row.style_tags),
        colour_tags=list(row.colour_tags),
        brands_to_avoid=list(row.brands_to_avoid),
        body_shape=row.body_shape,
        gender=row.gender,
        birth_date=row.birth_date,
        height=row.height,
        top_size=row.top_size,
        bottom_size=row.bottom_size,
        shoe_size=row.shoe_size,
        notifications_enabled=row.notifications_enabled,
    )


def get_or_default(session: Session, user_id: str) -> ProfileResponse:
    """FR-015: no saved row yet is the expected first-time state, not an error."""
    row = session.execute(
        text(
            "select style_tags, colour_tags, brands_to_avoid, body_shape, gender, birth_date, "
            "height, top_size, bottom_size, shoe_size, notifications_enabled "
            "from user_profile where user_id = :user_id"
        ),
        {"user_id": user_id},
    ).first()
    if row is None:
        return ProfileResponse()
    return _row_to_response(row)


def upsert_style_preferences(session: Session, user_id: str, update: StylePreferencesUpdate) -> ProfileResponse:
    row = session.execute(
        text(
            """
            insert into user_profile (user_id, style_tags, colour_tags, brands_to_avoid)
            values (:user_id, :style_tags, :colour_tags, :brands_to_avoid)
            on conflict (user_id) do update set
                style_tags = excluded.style_tags,
                colour_tags = excluded.colour_tags,
                brands_to_avoid = excluded.brands_to_avoid
            returning style_tags, colour_tags, brands_to_avoid, body_shape, gender, birth_date,
                height, top_size, bottom_size, shoe_size, notifications_enabled
            """
        ),
        {
            "user_id": user_id,
            "style_tags": update.style_tags,
            "colour_tags": update.colour_tags,
            "brands_to_avoid": update.brands_to_avoid,
        },
    ).one()
    session.commit()
    return _row_to_response(row)


def upsert_body_size(session: Session, user_id: str, update: BodySizeUpdate) -> ProfileResponse:
    row = session.execute(
        text(
            """
            insert into user_profile (
                user_id, body_shape, gender, birth_date, height, top_size, bottom_size, shoe_size
            )
            values (
                :user_id, :body_shape, :gender, :birth_date, :height, :top_size, :bottom_size,
                :shoe_size
            )
            on conflict (user_id) do update set
                body_shape = excluded.body_shape,
                gender = excluded.gender,
                birth_date = excluded.birth_date,
                height = excluded.height,
                top_size = excluded.top_size,
                bottom_size = excluded.bottom_size,
                shoe_size = excluded.shoe_size
            returning style_tags, colour_tags, brands_to_avoid, body_shape, gender, birth_date,
                height, top_size, bottom_size, shoe_size, notifications_enabled
            """
        ),
        {
            "user_id": user_id,
            "body_shape": update.body_shape,
            "gender": update.gender,
            "birth_date": update.birth_date,
            "height": update.height,
            "top_size": update.top_size,
            "bottom_size": update.bottom_size,
            "shoe_size": update.shoe_size,
        },
    ).one()
    session.commit()
    return _row_to_response(row)


def upsert_notifications(session: Session, user_id: str, update: NotificationsUpdate) -> ProfileResponse:
    row = session.execute(
        text(
            """
            insert into user_profile (user_id, notifications_enabled)
            values (:user_id, :notifications_enabled)
            on conflict (user_id) do update set
                notifications_enabled = excluded.notifications_enabled
            returning style_tags, colour_tags, brands_to_avoid, body_shape, gender, birth_date,
                height, top_size, bottom_size, shoe_size, notifications_enabled
            """
        ),
        {"user_id": user_id, "notifications_enabled": update.notifications_enabled},
    ).one()
    session.commit()
    return _row_to_response(row)
