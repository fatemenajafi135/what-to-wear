"""Database-backed calendar repository — `calendar_connections`,
`calendar_oauth_attempts`, and `picked_events` (migration `0004`).

Every method sets `request.jwt.claim.sub` first, matching
`repositories/supabase_closet.py`'s `_set_jwt_claim` convention: inert today
given this backend's bypass-privileged pooler connection
(specs/004-closet-read/research.md §1), but correct and forward-compatible
with the RLS convention `0001_init.sql` documents. The `WHERE user_id = ...`
on every query is the actual isolation guarantee for this backend's own
traffic, same as `supabase_closet.py`.

Tokens are encrypted before being written and decrypted only at the point a
live Google API call needs them (`adapters/token_encryption.py`) — never
returned from any method here as plaintext beyond that call site.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from whattowear.adapters import google_calendar, token_encryption
from whattowear.core.db import get_session

_session_scope = contextmanager(get_session)


def _set_jwt_claim(session: Session, user_id: str) -> None:
    session.execute(text("SELECT set_config('request.jwt.claim.sub', :user_id, true)"), {"user_id": user_id})


@dataclass(frozen=True)
class ConnectionStatus:
    connected: bool
    connected_at: datetime | None


@dataclass(frozen=True)
class PickedEventSnapshot:
    google_event_id: str
    title: str
    start_time: datetime
    location: str | None


class SupabaseCalendarRepository:
    def get_connection(self, user_id: str) -> ConnectionStatus:
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text("SELECT connected_at FROM calendar_connections WHERE user_id = :user_id"),
                {"user_id": user_id},
            ).fetchone()
            if row is None:
                return ConnectionStatus(connected=False, connected_at=None)
            return ConnectionStatus(connected=True, connected_at=row._mapping["connected_at"])

    def start_oauth_attempt(self, user_id: str) -> tuple[str, str]:
        """Generates a PKCE pair, stores the verifier keyed by a new `state`,
        and returns `(state, authorize_url)`."""
        pair = google_calendar.generate_pkce_pair()
        state = str(uuid.uuid4())
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            session.execute(
                text(
                    "INSERT INTO calendar_oauth_attempts (state, user_id, code_verifier)"
                    " VALUES (:state, :user_id, :code_verifier)"
                ),
                {"state": state, "user_id": user_id, "code_verifier": pair.verifier},
            )
            session.commit()
        authorize_url = google_calendar.build_authorize_url(state, pair.challenge)
        return state, authorize_url

    def finish_oauth_attempt(self, user_id: str, state: str, code: str) -> bool:
        """Looks up and deletes the pending attempt, verifies it belongs to
        `user_id`, exchanges the code for tokens, and persists the
        connection. Returns `False` (no exception) for any not-found/
        ownership/exchange failure — the route maps that to a generic 400
        without ever learning why, so no Google error detail can leak."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text("SELECT user_id, code_verifier FROM calendar_oauth_attempts WHERE state = :state"),
                {"state": state},
            ).fetchone()
            if row is None or str(row._mapping["user_id"]) != user_id:
                return False
            code_verifier = row._mapping["code_verifier"]
            session.execute(text("DELETE FROM calendar_oauth_attempts WHERE state = :state"), {"state": state})
            session.commit()

        try:
            grant = google_calendar.exchange_code_for_tokens(code, code_verifier)
        except google_calendar.GoogleCalendarRequestFailed:
            return False
        if grant.refresh_token is None:
            # No refresh token means Google didn't grant offline access —
            # can happen if consent wasn't re-prompted; treat as a failed
            # attempt rather than persisting a connection with no way to
            # refresh (research.md §6 depends on always having one).
            return False

        self._save_connection(user_id, grant.access_token, grant.refresh_token, grant.expires_at)
        return True

    def _save_connection(self, user_id: str, access_token: str, refresh_token: str, expires_at: datetime) -> None:
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            session.execute(
                text(
                    "INSERT INTO calendar_connections"
                    " (user_id, access_token_encrypted, refresh_token_encrypted, token_expires_at)"
                    " VALUES (:user_id, :access_token, :refresh_token, :expires_at)"
                    " ON CONFLICT (user_id) DO UPDATE SET"
                    "   access_token_encrypted = EXCLUDED.access_token_encrypted,"
                    "   refresh_token_encrypted = EXCLUDED.refresh_token_encrypted,"
                    "   token_expires_at = EXCLUDED.token_expires_at"
                ),
                {
                    "user_id": user_id,
                    "access_token": token_encryption.encrypt(access_token),
                    "refresh_token": token_encryption.encrypt(refresh_token),
                    "expires_at": expires_at,
                },
            )
            session.commit()

    def disconnect(self, user_id: str) -> None:
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            session.execute(text("DELETE FROM calendar_connections WHERE user_id = :user_id"), {"user_id": user_id})
            session.execute(text("DELETE FROM picked_events WHERE user_id = :user_id"), {"user_id": user_id})
            session.commit()

    def get_valid_access_token(self, user_id: str) -> str | None:
        """Returns a live access token, refreshing first if the stored one
        has expired. Returns `None` if there is no connection, or if a
        refresh attempt fails — in the latter case the connection (and any
        picked event) is deleted, so the caller is left indistinguishable
        from "never connected" (research.md §6)."""
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text(
                    "SELECT access_token_encrypted, refresh_token_encrypted, token_expires_at"
                    " FROM calendar_connections WHERE user_id = :user_id"
                ),
                {"user_id": user_id},
            ).fetchone()
        if row is None:
            return None

        expires_at: datetime = row._mapping["token_expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at > datetime.now(UTC):
            return token_encryption.decrypt(row._mapping["access_token_encrypted"])

        refresh_token = token_encryption.decrypt(row._mapping["refresh_token_encrypted"])
        try:
            grant = google_calendar.refresh_access_token(refresh_token)
        except google_calendar.GoogleCalendarRequestFailed:
            self.disconnect(user_id)
            return None

        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            session.execute(
                text(
                    "UPDATE calendar_connections SET access_token_encrypted = :access_token,"
                    " token_expires_at = :expires_at WHERE user_id = :user_id"
                ),
                {
                    "access_token": token_encryption.encrypt(grant.access_token),
                    "expires_at": grant.expires_at,
                    "user_id": user_id,
                },
            )
            session.commit()
        return grant.access_token

    def get_picked_event(self, user_id: str) -> PickedEventSnapshot | None:
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            row = session.execute(
                text("SELECT google_event_id, title, start_time, location FROM picked_events WHERE user_id = :user_id"),
                {"user_id": user_id},
            ).fetchone()
        if row is None:
            return None
        m = row._mapping
        return PickedEventSnapshot(
            google_event_id=m["google_event_id"], title=m["title"], start_time=m["start_time"], location=m["location"]
        )

    def set_picked_event(self, user_id: str, event: PickedEventSnapshot) -> None:
        with _session_scope() as session:
            _set_jwt_claim(session, user_id)
            session.execute(
                text(
                    "INSERT INTO picked_events (user_id, google_event_id, title, start_time, location)"
                    " VALUES (:user_id, :google_event_id, :title, :start_time, :location)"
                    " ON CONFLICT (user_id) DO UPDATE SET"
                    "   google_event_id = EXCLUDED.google_event_id,"
                    "   title = EXCLUDED.title,"
                    "   start_time = EXCLUDED.start_time,"
                    "   location = EXCLUDED.location,"
                    "   picked_at = now()"
                ),
                {
                    "user_id": user_id,
                    "google_event_id": event.google_event_id,
                    "title": event.title,
                    "start_time": event.start_time,
                    "location": event.location,
                },
            )
            session.commit()
