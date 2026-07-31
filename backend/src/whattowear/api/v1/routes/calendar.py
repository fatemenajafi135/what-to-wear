"""GET/POST /api/v1/calendar/* — see specs/012-calendar/contracts/calendar.md.

Every route depends on `get_current_user_id` (feature 003); `user_id` never
comes from a request body or query parameter. Ownership is enforced twice:
the repository's `WHERE user_id = ...` and RLS on all three tables (proven
independent of this backend's own connection by
tests/integration/test_calendar_rls.py).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from whattowear.adapters import google_calendar
from whattowear.auth import get_current_user_id
from whattowear.repositories.supabase_calendar import PickedEventSnapshot, SupabaseCalendarRepository

router = APIRouter()


def _get_repository() -> SupabaseCalendarRepository:
    return SupabaseCalendarRepository()


class ConnectionResponse(BaseModel):
    connected: bool
    connected_at: datetime | None


class AuthorizeUrlResponse(BaseModel):
    authorize_url: str


class ConnectFinishRequest(BaseModel):
    code: str
    state: str


class CalendarEventView(BaseModel):
    google_event_id: str
    title: str
    start: datetime
    location: str | None


class EventsResponse(BaseModel):
    events: list[CalendarEventView]


class PickedEventView(BaseModel):
    picked: bool
    event: CalendarEventView | None


class PickedEventRequest(BaseModel):
    google_event_id: str
    title: str
    start: datetime
    location: str | None


@router.get("/calendar/connection")
def get_connection(
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseCalendarRepository = Depends(_get_repository),  # noqa: B008
) -> ConnectionResponse:
    status_ = repository.get_connection(user_id)
    return ConnectionResponse(connected=status_.connected, connected_at=status_.connected_at)


@router.post("/calendar/connect/start")
def start_connect(
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseCalendarRepository = Depends(_get_repository),  # noqa: B008
) -> AuthorizeUrlResponse:
    try:
        _state, authorize_url = repository.start_oauth_attempt(user_id)
    except google_calendar.GoogleOAuthNotConfigured as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e
    return AuthorizeUrlResponse(authorize_url=authorize_url)


@router.post("/calendar/connect/finish")
def finish_connect(
    body: ConnectFinishRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseCalendarRepository = Depends(_get_repository),  # noqa: B008
) -> ConnectionResponse:
    ok = repository.finish_oauth_attempt(user_id, body.state, body.code)
    if not ok:
        # Deliberately generic — never echoes Google's own error body or the
        # code/verifier (spec.md FR-005).
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Could not complete calendar connection")
    status_ = repository.get_connection(user_id)
    return ConnectionResponse(connected=status_.connected, connected_at=status_.connected_at)


@router.post("/calendar/disconnect")
def disconnect(
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseCalendarRepository = Depends(_get_repository),  # noqa: B008
) -> ConnectionResponse:
    repository.disconnect(user_id)
    return ConnectionResponse(connected=False, connected_at=None)


@router.get("/calendar/events")
def list_events(
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseCalendarRepository = Depends(_get_repository),  # noqa: B008
) -> EventsResponse:
    access_token = repository.get_valid_access_token(user_id)
    if access_token is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Calendar not connected")
    try:
        events = google_calendar.list_upcoming_events(access_token)
    except google_calendar.GoogleCalendarRequestFailed as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Couldn't sync your calendar") from e
    return EventsResponse(
        events=[
            CalendarEventView(
                google_event_id=event.google_event_id, title=event.title, start=event.start, location=event.location
            )
            for event in events
        ]
    )


@router.get("/calendar/picked-event")
def get_picked_event(
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseCalendarRepository = Depends(_get_repository),  # noqa: B008
) -> PickedEventView:
    event = repository.get_picked_event(user_id)
    if event is None:
        return PickedEventView(picked=False, event=None)
    return PickedEventView(
        picked=True,
        event=CalendarEventView(
            google_event_id=event.google_event_id, title=event.title, start=event.start_time, location=event.location
        ),
    )


@router.put("/calendar/picked-event")
def set_picked_event(
    body: PickedEventRequest,
    user_id: str = Depends(get_current_user_id),  # noqa: B008
    repository: SupabaseCalendarRepository = Depends(_get_repository),  # noqa: B008
) -> PickedEventView:
    snapshot = PickedEventSnapshot(
        google_event_id=body.google_event_id, title=body.title, start_time=body.start, location=body.location
    )
    repository.set_picked_event(user_id, snapshot)
    return PickedEventView(
        picked=True,
        event=CalendarEventView(
            google_event_id=snapshot.google_event_id,
            title=snapshot.title,
            start=snapshot.start_time,
            location=snapshot.location,
        ),
    )
