"""
Integration tests for the insights router — GET /v1/insights/cost-summary.

Uses a real async PostgreSQL session (DATABASE_URL from env) and a minimal
FastAPI app that includes only the insights router, avoiding the
from __future__ import annotations issue in client_errors.py.

Engine and session factory are created fresh per test to avoid asyncio
event-loop reuse issues with asyncpg.
"""
from __future__ import annotations

import os
import time
import uuid
from decimal import Decimal
from unittest.mock import patch

import jwt as pyjwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import MagicMock
from cryptography.hazmat.primitives.asymmetric.ec import generate_private_key, SECP256R1
from cryptography.hazmat.backends import default_backend

from app.core.database import get_db
from app.models.detection import DetectionRun, Insight
from app.routers.insights import router as insights_router

# ---------------------------------------------------------------------------
# EC keypair for test JWT signing (mirrors Supabase ES256 tokens)
# ---------------------------------------------------------------------------

_PRIVATE_KEY = generate_private_key(SECP256R1(), default_backend())
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

_RAW_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@db:5432/revenue_recovery",
)
_ASYNC_DB_URL = (
    _RAW_DB_URL
    .replace("postgresql+psycopg://", "postgresql+asyncpg://")
    .replace("postgresql://", "postgresql+asyncpg://")
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_jwks_client():
    signing_key = MagicMock()
    signing_key.key = _PUBLIC_KEY
    client = MagicMock()
    client.get_signing_key_from_jwt.return_value = signing_key
    return client


def _make_token(org_id: str) -> str:
    payload = {
        "sub": str(uuid.uuid4()),
        "email": "test@example.com",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
        "app_metadata": {"organization_id": org_id},
    }
    return pyjwt.encode(payload, _PRIVATE_KEY, algorithm="ES256")


def _auth_header(org_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {_make_token(org_id)}"}


def _make_app(session_factory) -> FastAPI:
    """Return a minimal FastAPI app whose DB dependency is overridden."""

    async def _get_test_db():
        async with session_factory() as session:
            yield session

    app = FastAPI()
    app.include_router(insights_router)
    app.dependency_overrides[get_db] = _get_test_db
    return app


async def _seed_insight(
    session: AsyncSession,
    org_id: uuid.UUID,
    cost_usd: Decimal,
    model: str = "claude-sonnet-4-5",
) -> Insight:
    """Insert DetectionRun + Insight within an already-open session."""
    run = DetectionRun(
        organization_id=org_id,
        status="complete",
        rule_count=0,
        detection_count=0,
    )
    session.add(run)
    # Flush only the run to materialise its PK before building the Insight FK.
    await session.flush([run])

    insight = Insight(
        detection_run_id=run.id,
        organization_id=org_id,
        input_payload={},
        summary_text="Test insight",
        model=model,
        input_tokens=10,
        output_tokens=10,
        cost_usd=cost_usd,
    )
    session.add(insight)
    return insight


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cost_summary_returns_zero_when_no_insights():
    """Org with no insights → all zeros, by_model empty."""
    org_id = str(uuid.uuid4())

    engine = create_async_engine(_ASYNC_DB_URL, echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    app = _make_app(factory)

    with patch("app.auth.jwt._jwks_client", return_value=_mock_jwks_client()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/insights/cost-summary",
                headers=_auth_header(org_id),
            )

    await engine.dispose()

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["generation_count"] == 0
    assert data["total_cost_usd"] == 0.0
    assert data["avg_cost_usd"] == 0.0
    assert data["since"] is None
    assert data["by_model"] == {}


@pytest.mark.asyncio
async def test_cost_summary_aggregates_across_insights():
    """Two insights with known costs → totals and avg are correct."""
    org_id = uuid.uuid4()

    engine = create_async_engine(_ASYNC_DB_URL, echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    app = _make_app(factory)

    async with factory() as session:
        await _seed_insight(session, org_id, Decimal("0.0030"), model="claude-a")
        await _seed_insight(session, org_id, Decimal("0.0070"), model="claude-b")
        await session.commit()

    with patch("app.auth.jwt._jwks_client", return_value=_mock_jwks_client()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/insights/cost-summary",
                headers=_auth_header(str(org_id)),
            )

    await engine.dispose()

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["generation_count"] == 2
    assert data["total_cost_usd"] == pytest.approx(0.010, abs=1e-6)
    assert data["avg_cost_usd"] == pytest.approx(0.005, abs=1e-6)
    assert data["since"] is not None
    assert data["by_model"]["claude-a"] == pytest.approx(0.0030, abs=1e-6)
    assert data["by_model"]["claude-b"] == pytest.approx(0.0070, abs=1e-6)


@pytest.mark.asyncio
async def test_cost_summary_excludes_other_orgs():
    """Insight belonging to org B must not appear in org A's cost summary."""
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()

    engine = create_async_engine(_ASYNC_DB_URL, echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    app = _make_app(factory)

    async with factory() as session:
        await _seed_insight(session, org_a, Decimal("0.0050"))
        await _seed_insight(session, org_b, Decimal("0.9999"))
        await session.commit()

    with patch("app.auth.jwt._jwks_client", return_value=_mock_jwks_client()):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/v1/insights/cost-summary",
                headers=_auth_header(str(org_a)),
            )

    await engine.dispose()

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["generation_count"] == 1
    assert data["total_cost_usd"] == pytest.approx(0.0050, abs=1e-6)


@pytest.mark.asyncio
async def test_cost_summary_requires_auth():
    """Missing JWT → 401."""
    engine = create_async_engine(_ASYNC_DB_URL, echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    app = _make_app(factory)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/v1/insights/cost-summary")

    await engine.dispose()

    assert response.status_code == 401
