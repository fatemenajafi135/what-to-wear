"""Unit tests for auth.get_current_user_id.

JWKS fetch / signature verification is mocked — these tests exercise the
dependency's own logic (missing token, verification failure -> 401, valid
token -> sub claim returned), not network access to Supabase. Pattern
confirmed working in ../app-legacy/backend/tests/unit/test_auth.py.
"""

from __future__ import annotations

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from whattowear import auth


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_missing_credentials_rejected():
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user_id(credentials=None)
    assert exc_info.value.status_code == 401


def _mock_settings(mocker):
    mocker.patch.object(auth, "get_settings", return_value=mocker.Mock(supabase_jwt_aud="authenticated"))


def test_valid_token_returns_user_id(mocker):
    _mock_settings(mocker)
    fake_signing_key = mocker.Mock(key="fake-public-key")
    mocker.patch.object(
        auth,
        "_get_jwk_client",
        return_value=mocker.Mock(get_signing_key_from_jwt=mocker.Mock(return_value=fake_signing_key)),
    )
    mocker.patch.object(auth, "jwt_decode", return_value={"sub": "user-123", "aud": "authenticated"})

    user_id = auth.get_current_user_id(credentials=_creds("valid.jwt.token"))

    assert user_id == "user-123"


def test_invalid_signature_rejected(mocker):
    _mock_settings(mocker)
    fake_signing_key = mocker.Mock(key="fake-public-key")
    mocker.patch.object(
        auth,
        "_get_jwk_client",
        return_value=mocker.Mock(get_signing_key_from_jwt=mocker.Mock(return_value=fake_signing_key)),
    )
    mocker.patch.object(auth, "jwt_decode", side_effect=jwt.InvalidSignatureError("bad signature"))

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user_id(credentials=_creds("tampered.jwt.token"))
    assert exc_info.value.status_code == 401


def test_expired_token_rejected(mocker):
    _mock_settings(mocker)
    fake_signing_key = mocker.Mock(key="fake-public-key")
    mocker.patch.object(
        auth,
        "_get_jwk_client",
        return_value=mocker.Mock(get_signing_key_from_jwt=mocker.Mock(return_value=fake_signing_key)),
    )
    mocker.patch.object(auth, "jwt_decode", side_effect=jwt.ExpiredSignatureError("expired"))

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user_id(credentials=_creds("expired.jwt.token"))
    assert exc_info.value.status_code == 401


# --- get_current_access_token (feature 006) ---------------------------------


def test_missing_credentials_rejected_for_access_token():
    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_access_token(credentials=None)
    assert exc_info.value.status_code == 401


def test_valid_token_returns_raw_token(mocker):
    _mock_settings(mocker)
    fake_signing_key = mocker.Mock(key="fake-public-key")
    mocker.patch.object(
        auth,
        "_get_jwk_client",
        return_value=mocker.Mock(get_signing_key_from_jwt=mocker.Mock(return_value=fake_signing_key)),
    )
    mocker.patch.object(auth, "jwt_decode", return_value={"sub": "user-123", "aud": "authenticated"})

    token = auth.get_current_access_token(credentials=_creds("valid.jwt.token"))

    assert token == "valid.jwt.token"


def test_invalid_signature_rejected_for_access_token(mocker):
    _mock_settings(mocker)
    fake_signing_key = mocker.Mock(key="fake-public-key")
    mocker.patch.object(
        auth,
        "_get_jwk_client",
        return_value=mocker.Mock(get_signing_key_from_jwt=mocker.Mock(return_value=fake_signing_key)),
    )
    mocker.patch.object(auth, "jwt_decode", side_effect=jwt.InvalidSignatureError("bad signature"))

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_access_token(credentials=_creds("tampered.jwt.token"))
    assert exc_info.value.status_code == 401
