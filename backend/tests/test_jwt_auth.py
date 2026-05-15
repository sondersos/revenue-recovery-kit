"""
Unit tests for JWT authentication — decode_supabase_jwt and get_current_user.
Uses a test secret; never hits real Supabase.
"""
from __future__ import annotations

import time
import uuid
import pytest
import jwt as pyjwt
from unittest.mock import patch
from fastapi import HTTPException

from app.auth.jwt import decode_supabase_jwt, get_current_user, CurrentUser

TEST_SECRET = "test-jwt-secret-32-chars-exactly!!"
TEST_ORG_ID = str(uuid.uuid4())
TEST_USER_ID = str(uuid.uuid4())


def _make_token(
    secret: str = TEST_SECRET,
    exp_offset: int = 3600,
    audience: str = "authenticated",
    sub: str = TEST_USER_ID,
    email: str = "test@example.com",
    org_id: str | None = TEST_ORG_ID,
) -> str:
    payload: dict = {
        "sub": sub,
        "email": email,
        "aud": audience,
        "exp": int(time.time()) + exp_offset,
        "iat": int(time.time()),
    }
    if org_id is not None:
        payload["app_metadata"] = {"organization_id": org_id}
    return pyjwt.encode(payload, secret, algorithm="HS256")


# ---------------------------------------------------------------------------
# decode_supabase_jwt
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_decode_valid_token():
    token = _make_token()
    with patch("app.auth.jwt.settings") as mock_settings:
        mock_settings.SUPABASE_JWT_SECRET = TEST_SECRET
        payload = decode_supabase_jwt(token)
    assert payload["sub"] == TEST_USER_ID
    assert payload["email"] == "test@example.com"


@pytest.mark.unit
def test_decode_expired_token_raises():
    token = _make_token(exp_offset=-10)
    with patch("app.auth.jwt.settings") as mock_settings:
        mock_settings.SUPABASE_JWT_SECRET = TEST_SECRET
        with pytest.raises(ValueError, match="expired"):
            decode_supabase_jwt(token)


@pytest.mark.unit
def test_decode_wrong_secret_raises():
    token = _make_token(secret="correct-secret-32-chars-exactly!!")
    with patch("app.auth.jwt.settings") as mock_settings:
        mock_settings.SUPABASE_JWT_SECRET = "wrong-secret-32-chars-exactly!!!"
        with pytest.raises(ValueError):
            decode_supabase_jwt(token)


@pytest.mark.unit
def test_decode_wrong_audience_raises():
    token = _make_token(audience="wrong-audience")
    with patch("app.auth.jwt.settings") as mock_settings:
        mock_settings.SUPABASE_JWT_SECRET = TEST_SECRET
        with pytest.raises(ValueError, match="audience"):
            decode_supabase_jwt(token)


@pytest.mark.unit
def test_decode_missing_secret_raises():
    token = _make_token()
    with patch("app.auth.jwt.settings") as mock_settings:
        mock_settings.SUPABASE_JWT_SECRET = ""
        with pytest.raises(ValueError, match="not configured"):
            decode_supabase_jwt(token)


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user_returns_current_user():
    token = _make_token()
    with patch("app.auth.jwt.settings") as mock_settings:
        mock_settings.SUPABASE_JWT_SECRET = TEST_SECRET
        user = await get_current_user(authorization=f"Bearer {token}")
    assert isinstance(user, CurrentUser)
    assert user.user_id == TEST_USER_ID
    assert user.organization_id == TEST_ORG_ID
    assert user.email == "test@example.com"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user_missing_header_raises_401():
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization="")
    assert exc_info.value.status_code == 401


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user_no_bearer_prefix_raises_401():
    token = _make_token()
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization=token)
    assert exc_info.value.status_code == 401


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user_expired_token_raises_401():
    token = _make_token(exp_offset=-10)
    with patch("app.auth.jwt.settings") as mock_settings:
        mock_settings.SUPABASE_JWT_SECRET = TEST_SECRET
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 401


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user_wrong_secret_raises_401():
    token = _make_token(secret="other-secret-32-chars-exactly!!!")
    with patch("app.auth.jwt.settings") as mock_settings:
        mock_settings.SUPABASE_JWT_SECRET = TEST_SECRET
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 401


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user_falls_back_to_user_id_when_no_org():
    """When app_metadata has no org_id, fall back to user_id as org."""
    token = _make_token(org_id=None)
    with patch("app.auth.jwt.settings") as mock_settings:
        mock_settings.SUPABASE_JWT_SECRET = TEST_SECRET
        user = await get_current_user(authorization=f"Bearer {token}")
    assert user.organization_id == TEST_USER_ID
