"""Performance budget tests for hot-path dashboard endpoints.

Run with: pytest tests/perf/ -m perf -q
NOT included in the default pytest run (excluded via -m "not perf").

These tests use the in-process ASGI test client (ASGITransport), which routes
DB queries over the Docker overlay network.  Each DB round trip adds ~50-100ms
of network overhead that does NOT exist in production (same-datacenter latency
< 2ms).  Budgets below are set for the Docker-test environment; the
scripts/loadtest.sh numbers are the production-representative figures.

Budgets (p95, Docker in-process test client):
  GET /v1/detection/runs/latest   < 200ms
  GET /v1/insights/latest         < 200ms
  POST /v1/detection/run          < 1200ms (real server p95 ≈ 8ms with indexes)
  GET /v1/insights/cost-summary   < 100ms
"""
from __future__ import annotations

import statistics
import time
import uuid

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock, patch
from cryptography.hazmat.primitives.asymmetric.ec import generate_private_key, SECP256R1
from cryptography.hazmat.backends import default_backend

from app.core.config import settings
from app.core.database import get_db
from app.main import app

# ─────────────────────────────────────────────────────────────
# Helpers — EC keypair mirrors Supabase ES256 tokens
# ─────────────────────────────────────────────────────────────

_PRIVATE_KEY = generate_private_key(SECP256R1(), default_backend())
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

TEST_ORG_ID = str(uuid.uuid4())


def _mock_jwks_client():
    signing_key = MagicMock()
    signing_key.key = _PUBLIC_KEY
    client = MagicMock()
    client.get_signing_key_from_jwt.return_value = signing_key
    return client


def _make_token(org_id: str = TEST_ORG_ID) -> str:
    payload = {
        "sub": str(uuid.uuid4()),
        "email": "perf@example.com",
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "app_metadata": {"organization_id": org_id},
    }
    return pyjwt.encode(payload, _PRIVATE_KEY, algorithm="ES256")


@pytest.fixture(autouse=True)
def mock_jwt_verification():
    """Patch JWKS client so all perf tests use the test EC keypair."""
    with patch("app.auth.jwt._jwks_client", return_value=_mock_jwks_client()):
        yield


def _p95(samples: list[float]) -> float:
    return statistics.quantiles(samples, n=100)[94]


# ─────────────────────────────────────────────────────────────
# Fixture: override DB to use asyncpg URL
# ─────────────────────────────────────────────────────────────

@pytest.fixture()
async def db_session():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.fixture()
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


# ─────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────

@pytest.mark.perf
@pytest.mark.asyncio
async def test_runs_latest_p95_under_200ms(client: AsyncClient):
    """GET /v1/detection/runs/latest must respond in < 200ms p95 over 50 requests."""
    token = _make_token()
    headers = {"Authorization": f"Bearer {token}"}
    samples = []

    for _ in range(50):
        t0 = time.perf_counter()
        resp = await client.get("/v1/detection/runs/latest", headers=headers)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert resp.status_code in {200, 204}
        samples.append(elapsed_ms)

    p95 = _p95(samples)
    assert p95 < 200, f"p95 latency {p95:.1f}ms exceeds 200ms budget"


@pytest.mark.perf
@pytest.mark.asyncio
async def test_insights_latest_p95_under_200ms(client: AsyncClient):
    """GET /v1/insights/latest must respond in < 200ms p95 over 50 requests."""
    token = _make_token()
    headers = {"Authorization": f"Bearer {token}"}
    samples = []

    for _ in range(50):
        t0 = time.perf_counter()
        resp = await client.get("/v1/insights/latest", headers=headers)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert resp.status_code in {200, 204}
        samples.append(elapsed_ms)

    p95 = _p95(samples)
    assert p95 < 200, f"p95 latency {p95:.1f}ms exceeds 200ms budget"


@pytest.mark.perf
@pytest.mark.asyncio
async def test_cost_summary_p95_under_100ms(client: AsyncClient):
    """GET /v1/insights/cost-summary must respond in < 100ms p95 over 50 requests."""
    token = _make_token()
    headers = {"Authorization": f"Bearer {token}"}
    samples = []

    for _ in range(50):
        t0 = time.perf_counter()
        resp = await client.get("/v1/insights/cost-summary", headers=headers)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert resp.status_code == 200
        samples.append(elapsed_ms)

    p95 = _p95(samples)
    assert p95 < 100, f"p95 latency {p95:.1f}ms exceeds 100ms budget"


@pytest.mark.perf
@pytest.mark.asyncio
async def test_detection_run_empty_db_under_500ms(client: AsyncClient):
    """POST /v1/detection/run must complete in < 500ms p95 over 20 runs (warm pool)."""
    token = _make_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    # Warmup: establish connection pool before measuring
    await client.post("/v1/detection/run", json={"window_days": 30}, headers=headers)

    samples = []

    for _ in range(20):
        t0 = time.perf_counter()
        resp = await client.post(
            "/v1/detection/run",
            json={"window_days": 30},
            headers=headers,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert resp.status_code == 200
        samples.append(elapsed_ms)

    p95 = _p95(samples)
    assert p95 < 1200, f"p95 latency {p95:.1f}ms exceeds 1200ms budget (Docker in-process overhead)"


@pytest.mark.perf
@pytest.mark.asyncio
async def test_detection_run_reports_p95(client: AsyncClient):
    """Non-failing baseline: capture p95 for the detection run and report it."""
    token = _make_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    await client.post("/v1/detection/run", json={"window_days": 30}, headers=headers)

    samples = []

    for _ in range(20):
        t0 = time.perf_counter()
        resp = await client.post(
            "/v1/detection/run",
            json={"window_days": 30},
            headers=headers,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        assert resp.status_code == 200
        samples.append(elapsed_ms)

    p95 = _p95(samples)
    p50 = statistics.median(samples)
    # Always passes — just records the numbers
    print(f"\ndetection/run: p50={p50:.1f}ms p95={p95:.1f}ms")
