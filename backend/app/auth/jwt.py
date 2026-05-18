"""
Supabase JWT verification for FastAPI.

Uses ES256 + JWKS endpoint (asymmetric keys). The JWKS client is
cached for 1 hour so key rotations are picked up automatically.
Never logs the full token, the raw signing key, or user PII beyond
the user_id hash in debug mode.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache

import jwt as pyjwt
from jwt import PyJWKClient
from fastapi import Header, HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CurrentUser:
    user_id: str
    organization_id: str
    email: str


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    """Return a module-level cached JWKS client. Keys refresh every hour."""
    url = settings.SUPABASE_JWKS_URL
    if not url:
        raise ValueError("SUPABASE_JWKS_URL is not configured")
    return PyJWKClient(url, cache_keys=True, lifespan=3600)


def decode_supabase_jwt(token: str) -> dict:
    """
    Verify a Supabase-issued JWT using ES256 + JWKS.
    Raises ValueError on any verification failure.
    """
    try:
        client = _jwks_client()
        signing_key = client.get_signing_key_from_jwt(token).key
        payload = pyjwt.decode(
            token,
            signing_key,
            algorithms=["ES256"],
            audience="authenticated",
            options={"verify_exp": True},
            leeway=10,
        )
        return payload
    except pyjwt.ExpiredSignatureError as exc:
        raise ValueError("Token has expired") from exc
    except pyjwt.InvalidAudienceError as exc:
        raise ValueError("Invalid token audience") from exc
    except pyjwt.InvalidSignatureError as exc:
        raise ValueError(f"InvalidSignature: {exc}") from exc
    except pyjwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"JWT verification failed: {exc}") from exc


async def get_current_user(
    authorization: str = Header(default=""),
) -> CurrentUser:
    """
    FastAPI dependency: parse Bearer token, verify JWT, return CurrentUser.
    Raises HTTP 401 on any failure.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="invalid_or_missing_token")

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="invalid_or_missing_token")

    try:
        payload = decode_supabase_jwt(token)
    except ValueError as exc:
        logger.debug("JWT verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="invalid_or_missing_token") from exc

    # Extract fields — check app_metadata first (admin-controlled), then
    # user_metadata as fallback (allows SQL-based setup during dev/demo).
    user_id = payload.get("sub", "")
    email = payload.get("email", "")
    app_metadata = payload.get("app_metadata") or {}
    user_metadata = payload.get("user_metadata") or {}
    organization_id = (
        app_metadata.get("organization_id")
        or user_metadata.get("organization_id")
        or ""
    )

    if not user_id:
        raise HTTPException(status_code=401, detail="invalid_or_missing_token")

    # Use user_id as org fallback for single-tenant dev (no org metadata set yet)
    if not organization_id:
        organization_id = user_id

    current_user = CurrentUser(
        user_id=user_id, organization_id=organization_id, email=email
    )

    # Propagate identifiers into ContextVars for structured logging
    from app.observability.correlation import org_id as _org_id, user_id as _user_id

    _org_id.set(current_user.organization_id)
    _user_id.set(current_user.user_id)

    return current_user
