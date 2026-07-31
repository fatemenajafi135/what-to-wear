"""adapters/token_encryption.py — round-trip encrypt/decrypt, and a clear
error when WTW_TOKEN_ENCRYPTION_KEY is unset, matching llm_gateway.py's
existing "raise clearly on missing config" pattern."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet

from whattowear.adapters import token_encryption
from whattowear.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_caches() -> None:
    get_settings.cache_clear()
    token_encryption._fernet.cache_clear()
    yield
    get_settings.cache_clear()
    token_encryption._fernet.cache_clear()


def _set_base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("SUPABASE_URL", "http://127.0.0.1:54321")


def test_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("WTW_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())

    ciphertext = token_encryption.encrypt("ya29.a0Ab-super-secret-access-token")
    assert ciphertext != "ya29.a0Ab-super-secret-access-token"
    assert token_encryption.decrypt(ciphertext) == "ya29.a0Ab-super-secret-access-token"


def test_encrypt_raises_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("WTW_TOKEN_ENCRYPTION_KEY", "")
    with pytest.raises(RuntimeError, match="WTW_TOKEN_ENCRYPTION_KEY"):
        token_encryption.encrypt("plaintext")


def test_decrypt_raises_on_tampered_ciphertext(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("WTW_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())

    ciphertext = token_encryption.encrypt("a-token")
    tampered = ciphertext[:-4] + "abcd"
    with pytest.raises(RuntimeError, match="could not be decrypted"):
        token_encryption.decrypt(tampered)
