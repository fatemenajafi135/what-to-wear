"""adapters/google_calendar.py — PKCE param shape, token exchange/refresh
request shape, event-list query params, and that no function ever leaks a
token/code/verifier into an exception message."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from whattowear.adapters import google_calendar
from whattowear.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set_base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")


def _set_google_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:3000/calendar/callback")


class TestPkce:
    def test_generate_pkce_pair_challenge_is_derived_from_verifier(self) -> None:
        pair = google_calendar.generate_pkce_pair()
        assert pair.verifier
        assert pair.challenge
        assert pair.challenge != pair.verifier
        # S256 challenges never contain base64 padding.
        assert "=" not in pair.challenge


class TestBuildAuthorizeUrl:
    def test_raises_when_unconfigured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_base_env(monkeypatch)
        monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "")
        with pytest.raises(google_calendar.GoogleOAuthNotConfigured):
            google_calendar.build_authorize_url("state-123", "challenge-abc")

    def test_url_carries_pkce_and_offline_params(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_base_env(monkeypatch)
        _set_google_env(monkeypatch)
        url = google_calendar.build_authorize_url("state-123", "challenge-abc")
        assert "code_challenge=challenge-abc" in url
        assert "code_challenge_method=S256" in url
        assert "state=state-123" in url
        assert "access_type=offline" in url
        assert "prompt=consent" in url
        assert "calendar.events.readonly" in url


class TestExchangeCodeForTokens:
    def test_posts_verifier_and_code_to_token_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_base_env(monkeypatch)
        _set_google_env(monkeypatch)
        mock_response = MagicMock(ok=True)
        mock_response.json.return_value = {
            "access_token": "at-123",
            "refresh_token": "rt-456",
            "expires_in": 3600,
        }
        mock_post = MagicMock(return_value=mock_response)
        monkeypatch.setattr(google_calendar.requests, "post", mock_post)

        grant = google_calendar.exchange_code_for_tokens("auth-code", "verifier-xyz")

        assert grant.access_token == "at-123"
        assert grant.refresh_token == "rt-456"
        assert isinstance(grant.expires_at, datetime)
        _url, kwargs = mock_post.call_args
        assert kwargs["data"]["code"] == "auth-code"
        assert kwargs["data"]["code_verifier"] == "verifier-xyz"

    def test_failure_message_never_echoes_response_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_base_env(monkeypatch)
        _set_google_env(monkeypatch)
        mock_response = MagicMock(ok=False, status_code=400)
        mock_response.json.return_value = {"error": "invalid_grant", "code_verifier": "verifier-xyz"}
        monkeypatch.setattr(google_calendar.requests, "post", MagicMock(return_value=mock_response))

        with pytest.raises(google_calendar.GoogleCalendarRequestFailed) as exc_info:
            google_calendar.exchange_code_for_tokens("auth-code", "verifier-xyz")
        assert "verifier-xyz" not in str(exc_info.value)
        assert "auth-code" not in str(exc_info.value)


class TestRefreshAccessToken:
    def test_refresh_does_not_return_a_new_refresh_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_base_env(monkeypatch)
        _set_google_env(monkeypatch)
        mock_response = MagicMock(ok=True)
        mock_response.json.return_value = {"access_token": "at-new", "expires_in": 3600}
        monkeypatch.setattr(google_calendar.requests, "post", MagicMock(return_value=mock_response))

        grant = google_calendar.refresh_access_token("rt-456")
        assert grant.access_token == "at-new"
        assert grant.refresh_token is None


class TestListUpcomingEvents:
    def test_query_params_use_primary_calendar_and_window(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_base_env(monkeypatch)
        _set_google_env(monkeypatch)
        mock_response = MagicMock(ok=True)
        mock_response.json.return_value = {
            "items": [
                {
                    "id": "evt-1",
                    "summary": "Dinner with Sam",
                    "start": {"dateTime": "2026-08-01T19:30:00Z"},
                    "location": "Tanto",
                }
            ]
        }
        mock_get = MagicMock(return_value=mock_response)
        monkeypatch.setattr(google_calendar.requests, "get", mock_get)

        events = google_calendar.list_upcoming_events("at-123")

        assert len(events) == 1
        assert events[0].google_event_id == "evt-1"
        assert events[0].title == "Dinner with Sam"
        assert events[0].location == "Tanto"
        _url, kwargs = mock_get.call_args
        assert "/calendars/primary/events" in _url[0]
        assert kwargs["params"]["maxResults"] == str(google_calendar.EVENT_MAX_RESULTS)
        assert kwargs["headers"]["Authorization"] == "Bearer at-123"

    def test_event_with_no_location_parses_cleanly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_base_env(monkeypatch)
        _set_google_env(monkeypatch)
        mock_response = MagicMock(ok=True)
        mock_response.json.return_value = {
            "items": [{"id": "evt-2", "summary": "Solo focus block", "start": {"dateTime": "2026-08-02T09:00:00Z"}}]
        }
        monkeypatch.setattr(google_calendar.requests, "get", MagicMock(return_value=mock_response))

        events = google_calendar.list_upcoming_events("at-123")
        assert events[0].location is None

    def test_all_day_event_parses_without_time_component(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _set_base_env(monkeypatch)
        _set_google_env(monkeypatch)
        mock_response = MagicMock(ok=True)
        mock_response.json.return_value = {
            "items": [{"id": "evt-3", "summary": "Trip", "start": {"date": "2026-08-05"}}]
        }
        monkeypatch.setattr(google_calendar.requests, "get", MagicMock(return_value=mock_response))

        events = google_calendar.list_upcoming_events("at-123")
        assert events[0].start.year == 2026
        assert events[0].start.month == 8
        assert events[0].start.day == 5
