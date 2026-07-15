"""FastAPI dependency verifying a Supabase JWT's signature locally.

Verifies with `pyjwt`'s `PyJWKClient` against the project's JWKS endpoint
(ES256 — Supabase's current recommended signing key; research.md confirmed
the project's active key is ES256, no HS256 fallback needed). The backend
holds only the public key, so a backend compromise can't mint tokens. No
local `users` table lookup — the verified `sub` claim is the user_id.
"""

from __future__ import annotations

import os

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
JWT_AUD = os.environ.get("SUPABASE_JWT_AUD", "authenticated")

_bearer = HTTPBearer(auto_error=False)
_jwk_client: PyJWKClient | None = None


def _get_jwk_client() -> PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        if not SUPABASE_URL:
            raise RuntimeError("SUPABASE_URL is required. Set it in .env (see .env.example).")
        _jwk_client = PyJWKClient(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json")
    return _jwk_client


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Verify the bearer token's signature and return the `sub` claim.

    Raises 401 on a missing, malformed, expired, or invalid-signature token.
    """
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = credentials.credentials
    try:
        signing_key = _get_jwk_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience=JWT_AUD,
        )
    except jwt.PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}") from e
    return payload["sub"]
