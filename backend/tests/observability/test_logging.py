"""
Tests for structured logging / correlation-ID propagation.

Uses FastAPI TestClient (synchronous WSGI adapter over ASGI) so no event-loop
fixtures are needed here.
"""

from __future__ import annotations

import logging
import sys
import pathlib


# Ensure backend/ is on sys.path (mirrors conftest.py)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.observability.logging import configure_logging
from app.middleware.request_context import RequestContextMiddleware


# ---------------------------------------------------------------------------
# Minimal test app — avoids pulling in DB / scheduler / third-party secrets
# ---------------------------------------------------------------------------


def _make_test_app() -> FastAPI:
    configure_logging()

    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)

    @test_app.get("/health")
    async def health():
        return {"status": "healthy"}

    @test_app.get("/boom")
    async def boom():
        raise RuntimeError("intentional test error")

    return test_app


_app = _make_test_app()
_client = TestClient(_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_correlation_id_present_in_all_logs(caplog):
    """
    Every log record emitted by our own middleware during a request must have
    correlation_id set.  Third-party records (httpx, etc.) that fire outside the
    ASGI context are excluded from the assertion.
    """
    with caplog.at_level(logging.INFO):
        response = _client.get("/health")

    assert response.status_code == 200

    # Filter to records produced by our own code
    our_records = [r for r in caplog.records if r.name.startswith("app.")]

    assert (
        len(our_records) >= 2
    ), f"Expected at least request.start and request.end records, got: {our_records}"

    for record in our_records:
        assert hasattr(
            record, "correlation_id"
        ), f"Record '{record.message}' is missing correlation_id attribute"
        assert (
            record.correlation_id is not None
        ), f"Record '{record.message}' has correlation_id=None"


def test_correlation_id_echoed_in_response_header():
    """The middleware must echo X-Request-ID back in the response."""
    response = _client.get("/health")
    assert response.status_code == 200
    assert (
        "x-request-id" in response.headers
    ), "Expected X-Request-ID header in response"
    assert response.headers["x-request-id"], "X-Request-ID must not be empty"


def test_provided_x_request_id_is_used():
    """If the client sends X-Request-ID the same value must be echoed back."""
    custom_id = "test-abc-123"
    response = _client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == custom_id, (
        f"Expected echoed X-Request-ID={custom_id!r}, "
        f"got {response.headers.get('x-request-id')!r}"
    )


def test_no_jwt_in_any_log_line(caplog):
    """
    No log record must contain a raw Bearer token.

    We make a request with a fake (non-verifiable) Authorization header and
    verify that the literal string 'Bearer ' followed by any token-like content
    does not appear in any log record's message or extra fields.
    """
    fake_token = "Bearer " + "a" * 64  # long enough to look like a real JWT

    with caplog.at_level(logging.DEBUG):
        _client.get("/health", headers={"Authorization": fake_token})

    for record in caplog.records:
        # Check the formatted message
        assert (
            "Bearer " not in record.getMessage()
        ), f"Found raw Bearer token in log message: {record.getMessage()!r}"
        # Check any extra attributes on the record
        for attr in vars(record).values():
            if isinstance(attr, str):
                assert (
                    "Bearer " not in attr
                ), f"Found raw Bearer token in log record attribute: {attr!r}"
