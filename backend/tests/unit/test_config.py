"""Tests for Settings configuration, especially CORS origins parsing."""

from __future__ import annotations

from whattowear.core.config import Settings


def test_cors_origins_default_to_localhost_when_unset() -> None:
    """When wtw_cors_origins is unset, defaults include both localhost and 127.0.0.1."""
    settings = Settings(database_url="dummy", supabase_url="dummy")
    assert settings.cors_allowed_origins == [
        "http://localhost:3000",
        "http://localhost:3100",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3100",
    ]


def test_cors_origins_strips_whitespace() -> None:
    """Whitespace around origins is stripped, preventing 'origin: ' mismatches."""
    settings = Settings(
        database_url="dummy",
        supabase_url="dummy",
        wtw_cors_origins="https://app.example.com, https://staging.example.com",
    )
    assert settings.cors_allowed_origins == [
        "https://app.example.com",
        "https://staging.example.com",
    ]


def test_cors_origins_filters_empty_entries() -> None:
    """Trailing commas and empty entries are filtered out."""
    settings = Settings(
        database_url="dummy",
        supabase_url="dummy",
        wtw_cors_origins="https://app.example.com,,https://staging.example.com,",
    )
    assert settings.cors_allowed_origins == [
        "https://app.example.com",
        "https://staging.example.com",
    ]


def test_cors_origins_handles_mixed_whitespace_and_empty() -> None:
    """Both whitespace stripping and empty filtering work together."""
    settings = Settings(
        database_url="dummy",
        supabase_url="dummy",
        wtw_cors_origins="  https://app.example.com  , , https://staging.example.com  , ",
    )
    assert settings.cors_allowed_origins == [
        "https://app.example.com",
        "https://staging.example.com",
    ]


def test_cors_origins_empty_string_defaults_to_localhost() -> None:
    """An empty string is treated the same as unset."""
    settings = Settings(database_url="dummy", supabase_url="dummy", wtw_cors_origins="")
    assert settings.cors_allowed_origins == [
        "http://localhost:3000",
        "http://localhost:3100",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3100",
    ]


def test_cors_origins_whitespace_only_defaults_to_localhost() -> None:
    """Whitespace-only string filters to empty and defaults to localhost."""
    settings = Settings(database_url="dummy", supabase_url="dummy", wtw_cors_origins="  ,  ,  ")
    assert settings.cors_allowed_origins == [
        "http://localhost:3000",
        "http://localhost:3100",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3100",
    ]
