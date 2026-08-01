"""FastAPI dependency verifying a Supabase JWT's signature locally.

Verifies with `pyjwt`'s `PyJWKClient` against the project's JWKS endpoint
(ES256 — Supabase's current default signing key for new local/cloud
projects; see specs/003-auth/research.md §2). The backend holds only the
public key, so a backend compromise can't mint tokens. No local `users`
table lookup — the verified `sub` claim is the user id.

Adapted from ../app-legacy/backend/src/whattowear/auth.py onto this
package's `get_settings()` pattern rather than raw `os.environ` +
`load_dotenv` (research.md §2's "port and adapt", not copy verbatim).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWTError
from jwt import decode as jwt_decode

from whattowear.core.config import get_settings

_bearer = HTTPBearer(auto_error=False)
_jwk_client: PyJWKClient | None = None


def _get_jwk_client() -> PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        settings = get_settings()
        _jwk_client = PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")
    return _jwk_client


def _verify(credentials: HTTPAuthorizationCredentials | None) -> tuple[str, dict]:
    """Shared verification: raises 401 on a missing, malformed, expired, or
    invalid-signature token — all as the same outcome, so a caller can't
    distinguish "no token" from "bad token" from the response alone (spec.md
    FR-015). Returns the raw token alongside the decoded payload so callers
    needing either (or both — feature 006's Storage calls need the raw
    token, everything else needs just `sub`) don't re-verify twice."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = credentials.credentials
    try:
        signing_key = _get_jwk_client().get_signing_key_from_jwt(token)
        payload = jwt_decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience=get_settings().supabase_jwt_aud,
        )
    except PyJWTError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {e}") from e
    return token, payload


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
) -> str:
    """Verify the bearer token's signature and return the `sub` claim."""
    _token, payload = _verify(credentials)
    return str(payload["sub"])


def get_current_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),  # noqa: B008
) -> str:
    """Verify the bearer token's signature and return the raw token itself.

    Feature 006: Storage uploads and signed-URL generation must use the
    caller's own bearer token, never a service-role key — the per-user
    Storage RLS policy is what enforces isolation there, not application
    code (specs/006-photo-upload-vision/research.md §1)."""
    token, _payload = _verify(credentials)
    return token
