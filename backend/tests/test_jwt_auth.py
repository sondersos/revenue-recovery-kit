"""
Unit tests for JWT authentication — decode_supabase_jwt and get_current_user.

Uses a generated EC P-256 keypair that mirrors what Supabase issues (ES256).
The JWKS client is monkeypatched so tests never hit the real Supabase endpoint.
"""

from __future__ import annotations

import time
import uuid
import pytest
import jwt as pyjwt
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from cryptography.hazmat.primitives.asymmetric.ec import generate_private_key, SECP256R1
from cryptography.hazmat.backends import default_backend

from app.auth.jwt import decode_supabase_jwt, get_current_user, CurrentUser

# ---------------------------------------------------------------------------
# Test EC keypair (generated once per test session)
# ---------------------------------------------------------------------------

_PRIVATE_KEY = generate_private_key(SECP256R1(), default_backend())
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

_WRONG_PRIVATE_KEY = generate_private_key(SECP256R1(), default_backend())

TEST_ORG_ID = str(uuid.uuid4())
TEST_USER_ID = str(uuid.uuid4())


def _make_token(
    private_key=_PRIVATE_KEY,
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
    return pyjwt.encode(payload, private_key, algorithm="ES256")


def _mock_jwks_client(public_key=_PUBLIC_KEY):
    """Return a mock JWKS client that always yields the given public key."""
    signing_key = MagicMock()
    signing_key.key = public_key
    client = MagicMock()
    client.get_signing_key_from_jwt.return_value = signing_key
    return client


# ---------------------------------------------------------------------------
# decode_supabase_jwt — positive cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_decode_valid_es256_token():
    token = _make_token()
    with patch("app.auth.jwt._jwks_client", return_value=_mock_jwks_client()):
        payload = decode_supabase_jwt(token)
    assert payload["sub"] == TEST_USER_ID
    assert payload["email"] == "test@example.com"
    assert payload["app_metadata"]["organization_id"] == TEST_ORG_ID


@pytest.mark.unit
def test_decode_extracts_app_metadata_org_id():
    token = _make_token()
    with patch("app.auth.jwt._jwks_client", return_value=_mock_jwks_client()):
        payload = decode_supabase_jwt(token)
    assert payload["app_metadata"]["organization_id"] == TEST_ORG_ID


# ---------------------------------------------------------------------------
# decode_supabase_jwt — negative cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_decode_expired_token_raises():
    token = _make_token(exp_offset=-10)
    with patch("app.auth.jwt._jwks_client", return_value=_mock_jwks_client()):
        with pytest.raises(ValueError, match="expired"):
            decode_supabase_jwt(token)


@pytest.mark.unit
def test_decode_wrong_signing_key_raises_invalid_signature():
    """Token signed with a different EC key must be rejected with InvalidSignature."""
    token = _make_token(private_key=_WRONG_PRIVATE_KEY)
    # JWKS client returns the correct PUBLIC key — signature will not match
    with patch(
        "app.auth.jwt._jwks_client", return_value=_mock_jwks_client(_PUBLIC_KEY)
    ):
        with pytest.raises(ValueError, match="InvalidSignature"):
            decode_supabase_jwt(token)


@pytest.mark.unit
def test_decode_wrong_audience_raises():
    token = _make_token(audience="wrong-audience")
    with patch("app.auth.jwt._jwks_client", return_value=_mock_jwks_client()):
        with pytest.raises(ValueError, match="audience"):
            decode_supabase_jwt(token)


@pytest.mark.unit
def test_decode_unconfigured_jwks_url_raises():
    """If SUPABASE_JWKS_URL is empty, _jwks_client raises ValueError."""
    # Clear the lru_cache so the unconfigured setting is exercised
    from app.auth.jwt import _jwks_client

    _jwks_client.cache_clear()
    with patch("app.auth.jwt.settings") as mock_settings:
        mock_settings.SUPABASE_JWKS_URL = ""
        token = _make_token()
        with pytest.raises(ValueError, match="not configured"):
            decode_supabase_jwt(token)
    # Restore cache so later tests work
    _jwks_client.cache_clear()


# ---------------------------------------------------------------------------
# get_current_user — happy path
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user_returns_current_user():
    token = _make_token()
    with patch("app.auth.jwt._jwks_client", return_value=_mock_jwks_client()):
        user = await get_current_user(authorization=f"Bearer {token}")
    assert isinstance(user, CurrentUser)
    assert user.user_id == TEST_USER_ID
    assert user.organization_id == TEST_ORG_ID
    assert user.email == "test@example.com"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user_falls_back_to_user_id_when_no_org():
    """When app_metadata has no org_id, fall back to user_id as org."""
    token = _make_token(org_id=None)
    with patch("app.auth.jwt._jwks_client", return_value=_mock_jwks_client()):
        user = await get_current_user(authorization=f"Bearer {token}")
    assert user.organization_id == TEST_USER_ID


# ---------------------------------------------------------------------------
# get_current_user — 401 cases
# ---------------------------------------------------------------------------


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
    with patch("app.auth.jwt._jwks_client", return_value=_mock_jwks_client()):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 401


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_current_user_wrong_signing_key_raises_401():
    """Token signed by a different EC key must yield HTTP 401."""
    token = _make_token(private_key=_WRONG_PRIVATE_KEY)
    with patch(
        "app.auth.jwt._jwks_client", return_value=_mock_jwks_client(_PUBLIC_KEY)
    ):
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(authorization=f"Bearer {token}")
    assert exc_info.value.status_code == 401
