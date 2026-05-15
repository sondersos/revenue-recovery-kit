"""
Supabase JWT verification for FastAPI.

Uses HS256 + SUPABASE_JWT_SECRET. Never logs the secret, the full token,
or user PII beyond the user_id hash in debug mode.
"""
import logging
from dataclasses import dataclass

import jwt as pyjwt
from fastapi import Header, HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class CurrentUser:
    user_id: str
    organization_id: str
    email: str


def decode_supabase_jwt(token: str) -> dict:
    """
    Verify a Supabase-issued JWT using HS256 + SUPABASE_JWT_SECRET.
    Raises ValueError on any verification failure.
    """
    secret = settings.SUPABASE_JWT_SECRET
    if not secret:
        raise ValueError("SUPABASE_JWT_SECRET is not configured")

    try:
        payload = pyjwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_exp": True},
        )
        return payload
    except pyjwt.ExpiredSignatureError as exc:
        raise ValueError("Token has expired") from exc
    except pyjwt.InvalidAudienceError as exc:
        raise ValueError("Invalid token audience") from exc
    except pyjwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc


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

    # Extract fields — Supabase puts org in app_metadata
    user_id = payload.get("sub", "")
    email = payload.get("email", "")
    app_metadata = payload.get("app_metadata") or {}
    organization_id = app_metadata.get("organization_id", "")

    if not user_id:
        raise HTTPException(status_code=401, detail="invalid_or_missing_token")

    # Use user_id as org fallback for single-tenant dev (no org metadata set yet)
    if not organization_id:
        organization_id = user_id

    return CurrentUser(user_id=user_id, organization_id=organization_id, email=email)
