"""
Unit tests for integrations.twilio.client.send_recovery_sms.

Uses respx to intercept httpx calls — no real HTTP is made.
The placeholder TWILIO_ACCOUNT_SID "ACtest000" is patched into settings
before any URL is constructed.
"""
import pytest
import httpx
import respx
from unittest.mock import patch

from integrations.twilio.client import send_recovery_sms


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

_TO_NUMBER = "+15550001234"
_MESSAGE = "Your payment failed."
_FAKE_SID = "ACtest000"
_TWILIO_URL = f"https://api.twilio.com/2010-04-01/Accounts/{_FAKE_SID}/Messages.json"


def _patch_settings():
    """Return a context-manager that replaces Twilio settings with test values."""
    return patch.multiple(
        "integrations.twilio.client.settings",
        TWILIO_ACCOUNT_SID=_FAKE_SID,
        TWILIO_AUTH_TOKEN="test_auth_token",
        TWILIO_FROM_NUMBER="+15550009999",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
@respx.mock
async def test_send_recovery_sms_happy_path_returns_sid():
    """
    A successful 200 response must return a dict and result in exactly
    1 HTTP call to the Twilio Messages endpoint.
    """
    respx.post(_TWILIO_URL).mock(
        return_value=httpx.Response(200, json={"sid": "SM_test_001", "status": "queued"})
    )

    with _patch_settings():
        with patch("integrations.twilio.client.asyncio.sleep", return_value=None):
            result = await send_recovery_sms(_TO_NUMBER, _MESSAGE)

    assert "sid" in result
    assert result["sid"] == "SM_test_001"
    assert respx.calls.call_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
@respx.mock
async def test_send_recovery_sms_retries_on_500_succeeds_on_third_attempt():
    """
    When the endpoint returns 500 twice then 200, send_recovery_sms must
    succeed and the total number of HTTP calls must be exactly 3.
    """
    respx.post(_TWILIO_URL).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(200, json={"sid": "SM_test_001", "status": "queued"}),
        ]
    )

    with _patch_settings():
        with patch("integrations.twilio.client.asyncio.sleep", return_value=None):
            result = await send_recovery_sms(_TO_NUMBER, _MESSAGE)

    assert respx.calls.call_count == 3
    assert "sid" in result


@pytest.mark.unit
@pytest.mark.asyncio
@respx.mock
async def test_send_recovery_sms_raises_after_exhausted_retries():
    """
    When the endpoint always returns 500, send_recovery_sms must raise
    RuntimeError after exactly 4 HTTP calls (attempt 0 + 3 retries).
    """
    respx.post(_TWILIO_URL).mock(
        return_value=httpx.Response(500)
    )

    with _patch_settings():
        with patch("integrations.twilio.client.asyncio.sleep", return_value=None):
            with pytest.raises(RuntimeError, match="Twilio failed after 3 retries"):
                await send_recovery_sms(_TO_NUMBER, _MESSAGE)

    assert respx.calls.call_count == 4
