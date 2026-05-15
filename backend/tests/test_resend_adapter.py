"""
Unit tests for integrations.resend.client.send_recovery_email.

Uses respx to intercept httpx calls — no real HTTP is made.
"""
import pytest
import httpx
import respx
from unittest.mock import patch

from integrations.resend.client import send_recovery_email


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_TO_EMAIL = "test@example.com"
_CONTACT_NAME = "Alex Sample"
_MESSAGE = "Your invoice is overdue."
_RESEND_URL = "https://api.resend.com/emails"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
@respx.mock
async def test_send_recovery_email_happy_path_returns_id():
    """
    A successful 200 response must return a dict containing 'id' and
    result in exactly 1 HTTP call.
    """
    respx.post(_RESEND_URL).mock(
        return_value=httpx.Response(200, json={"id": "msg_test_001"})
    )

    # Patch sleep so the test does not actually wait
    with patch("integrations.resend.client.asyncio.sleep", return_value=None):
        result = await send_recovery_email(_TO_EMAIL, _CONTACT_NAME, _MESSAGE)

    assert "id" in result
    assert result["id"] == "msg_test_001"
    assert respx.calls.call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
@respx.mock
async def test_send_recovery_email_retries_on_500_succeeds_on_third_attempt():
    """
    When the endpoint returns 500 twice then 200, send_recovery_email must
    succeed and the total number of HTTP calls must be exactly 3.
    """
    respx.post(_RESEND_URL).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(200, json={"id": "msg_test_001"}),
        ]
    )

    with patch("integrations.resend.client.asyncio.sleep", return_value=None):
        result = await send_recovery_email(_TO_EMAIL, _CONTACT_NAME, _MESSAGE)

    assert respx.calls.call_count == 3
    assert "id" in result


@pytest.mark.unit
@pytest.mark.asyncio
@respx.mock
async def test_send_recovery_email_raises_after_exhausted_retries():
    """
    When the endpoint always returns 500, send_recovery_email must raise
    RuntimeError after exactly 4 HTTP calls (attempt 0 + 3 retries).
    """
    respx.post(_RESEND_URL).mock(
        return_value=httpx.Response(500)
    )

    with patch("integrations.resend.client.asyncio.sleep", return_value=None):
        with pytest.raises(RuntimeError, match="Resend failed after 3 retries"):
            await send_recovery_email(_TO_EMAIL, _CONTACT_NAME, _MESSAGE)

    assert respx.calls.call_count == 4
