"""
Tests for /health and /healthz endpoints.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_client() -> TestClient:
    """Import app fresh and return a synchronous TestClient."""
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# /health — simple smoke test
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_health_ok():
    client = _make_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "healthy"}


# ---------------------------------------------------------------------------
# /healthz — DB + Anthropic probes
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_healthz_ok():
    """Both probes succeed → 200 with status 'ok'."""
    # Mock the DB dependency to return a session whose execute() succeeds
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())

    async def override_get_db():
        yield mock_session

    # Mock probe_anthropic to succeed
    async def mock_probe(timeout_s: float = 2.0) -> None:
        return None

    from app.main import app
    from app.core.database import get_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.routers.health.probe_anthropic", mock_probe):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/healthz")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["checks"]["db"] == "ok"
    assert data["checks"]["anthropic"] == "ok"


@pytest.mark.unit
def test_healthz_degraded_when_db_down():
    """DB execute raises → 503, status 'degraded', db check shows fail."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=Exception("db error"))

    async def override_get_db():
        yield mock_session

    async def mock_probe(timeout_s: float = 2.0) -> None:
        return None

    from app.main import app
    from app.core.database import get_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with patch("app.routers.health.probe_anthropic", mock_probe):
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/healthz")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["checks"]["db"] == "fail: Exception"
    assert data["checks"]["anthropic"] == "ok"


@pytest.mark.unit
def test_healthz_degraded_when_anthropic_key_missing():
    """ANTHROPIC_API_KEY is empty → anthropic probe fails → 503 degraded."""
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=MagicMock())

    async def override_get_db():
        yield mock_session

    from app.main import app
    from app.core.database import get_db
    from app.core.config import settings

    app.dependency_overrides[get_db] = override_get_db
    try:
        original_key = settings.ANTHROPIC_API_KEY
        settings.ANTHROPIC_API_KEY = ""
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/healthz")
    finally:
        settings.ANTHROPIC_API_KEY = original_key
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["checks"]["anthropic"].startswith("fail:")
