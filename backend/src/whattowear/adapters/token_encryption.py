"""Encrypts/decrypts calendar OAuth tokens at rest, using `cryptography`'s
`Fernet` (authenticated AES-128-CBC + HMAC) keyed by `WTW_TOKEN_ENCRYPTION_KEY`.

RLS alone doesn't protect these columns: this backend's own pooler
connection has BYPASSRLS (specs/004-closet-read/research.md §1), so a token
stored as plaintext would be readable by anyone with that same
bypass-privileged connection (Studio, a backup, a misconfigured future
access path) despite RLS being enabled on the table. See
specs/012-calendar/research.md §2 and docs/design-decisions.md §16 for the
full decision.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from whattowear.core.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    key = get_settings().wtw_token_encryption_key
    if not key:
        raise RuntimeError(
            "No token encryption key found. Set WTW_TOKEN_ENCRYPTION_KEY in .env "
            '(generate with: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())")'
        )
    try:
        return Fernet(key.encode())
    except ValueError as e:
        # A malformed key previously surfaced as a raw ValueError from deep
        # inside cryptography, arriving as a 500 at the very END of the OAuth
        # flow — after consent, after the token exchange, with the grant
        # already in hand and about to be discarded. The message named Fernet's
        # requirement but not the variable at fault or how to fix it.
        raise RuntimeError(
            f"WTW_TOKEN_ENCRYPTION_KEY is not a valid Fernet key ({e}). It must be "
            "32 url-safe base64-encoded bytes — any other base64 string will fail. "
            'Generate one with: python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        ) from e


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise RuntimeError("Stored calendar token could not be decrypted") from e
