"""Thin HTTP client for Google's OAuth and Calendar endpoints — no route or
database code, matching `adapters/`'s existing shape (`llm_gateway.py`). This
is a second, app-orchestrated PKCE flow, deliberately independent of feature
003's Supabase-brokered Google sign-in — see specs/012-calendar/research.md
§1 for why. Every function is call-time lazy (no environment read at import
time, matching `core.config.get_settings()`'s own guarantee).

No function here ever logs a token, authorization code, or PKCE verifier —
FR-005 (spec.md) is enforced at this boundary, not left to callers to
remember.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import requests

from whattowear.core.config import get_settings

_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

# Least-privilege: events only, no calendar-list/settings access
# (specs/012-calendar/research.md §4).
_SCOPE = "https://www.googleapis.com/auth/calendar.events.readonly"

EVENT_WINDOW_DAYS = 7
EVENT_MAX_RESULTS = 20


class GoogleOAuthNotConfigured(RuntimeError):
    """Raised when GOOGLE_OAUTH_CLIENT_ID/SECRET are unset (spec.md FR-017)."""


class GoogleCalendarRequestFailed(RuntimeError):
    """Raised when a live call to Google's token or Calendar API fails."""


@dataclass(frozen=True)
class PkcePair:
    verifier: str
    challenge: str


@dataclass(frozen=True)
class TokenGrant:
    access_token: str
    refresh_token: str | None
    expires_at: datetime


@dataclass(frozen=True)
class CalendarEvent:
    google_event_id: str
    title: str
    start: datetime
    location: str | None


def _require_client_credentials() -> tuple[str, str, str]:
    settings = get_settings()
    client_id = settings.google_oauth_client_id
    client_secret = settings.google_oauth_client_secret
    redirect_uri = settings.google_oauth_redirect_uri
    if not client_id or not client_secret or not redirect_uri:
        raise GoogleOAuthNotConfigured("Calendar connect isn't configured in this environment")
    return client_id, client_secret, redirect_uri


def generate_pkce_pair() -> PkcePair:
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return PkcePair(verifier=verifier, challenge=challenge)


def build_authorize_url(state: str, code_challenge: str) -> str:
    """Google's authorization endpoint. `access_type=offline` +
    `prompt=consent` so Google actually issues a refresh token — it only
    does so on first consent (or an explicit re-prompt) otherwise."""
    client_id, _client_secret, redirect_uri = _require_client_credentials()
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": _SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str, code_verifier: str) -> TokenGrant:
    client_id, client_secret, redirect_uri = _require_client_credentials()
    response = requests.post(
        _TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=10,
    )
    if not response.ok:
        # Never include the response body: it can echo back the code/verifier
        # context Google received (FR-005).
        raise GoogleCalendarRequestFailed(f"Google token exchange failed with status {response.status_code}")
    body = response.json()
    refresh_token = body.get("refresh_token")
    return TokenGrant(
        access_token=body["access_token"],
        refresh_token=refresh_token,
        expires_at=datetime.now(UTC) + timedelta(seconds=body["expires_in"]),
    )


def refresh_access_token(refresh_token: str) -> TokenGrant:
    """Google does not re-issue a refresh token on a refresh call — the
    caller keeps using the one it already has."""
    client_id, client_secret, _redirect_uri = _require_client_credentials()
    response = requests.post(
        _TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    if not response.ok:
        raise GoogleCalendarRequestFailed(f"Google token refresh failed with status {response.status_code}")
    body = response.json()
    return TokenGrant(
        access_token=body["access_token"],
        refresh_token=None,
        expires_at=datetime.now(UTC) + timedelta(seconds=body["expires_in"]),
    )


def list_upcoming_events(access_token: str) -> list[CalendarEvent]:
    """Primary calendar only, next `EVENT_WINDOW_DAYS` days, capped at
    `EVENT_MAX_RESULTS`, ordered by start time (specs/012-calendar/
    research.md §4)."""
    now = datetime.now(UTC)
    params = {
        "timeMin": now.isoformat(),
        "timeMax": (now + timedelta(days=EVENT_WINDOW_DAYS)).isoformat(),
        "maxResults": str(EVENT_MAX_RESULTS),
        "singleEvents": "true",
        "orderBy": "startTime",
    }
    response = requests.get(
        _EVENTS_URL,
        params=params,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if not response.ok:
        raise GoogleCalendarRequestFailed(f"Google Calendar events request failed with status {response.status_code}")
    items = response.json().get("items", [])
    return [_parse_event(item) for item in items if "start" in item]


def _parse_event(item: dict) -> CalendarEvent:
    start_field = item["start"]
    # All-day events carry "date" (no time component); timed events carry
    # "dateTime". Both are valid per Google's API — normalize to a UTC
    # datetime either way rather than assuming every event has a time.
    if "dateTime" in start_field:
        start = datetime.fromisoformat(start_field["dateTime"])
    else:
        start = datetime.fromisoformat(start_field["date"]).replace(tzinfo=UTC)
    return CalendarEvent(
        google_event_id=item["id"],
        title=item.get("summary", "(No title)"),
        start=start,
        location=item.get("location"),
    )
