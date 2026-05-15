import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RETRY_STATUSES = {429, 500, 502, 503, 504}
_BACKOFF_SECONDS = [1, 2, 4]


async def send_recovery_sms(to_number: str, message: str) -> dict:
    """Send a recovery SMS via Twilio with 3-retry exponential backoff.

    Does not log auth credentials, phone numbers, or message content.
    """
    url = (
        f"https://api.twilio.com/2010-04-01/Accounts"
        f"/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    )
    auth = (settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    data = {
        "From": settings.TWILIO_FROM_NUMBER,
        "To": to_number,
        "Body": message,
    }

    last_status_code: int | None = None

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt, backoff in enumerate([0] + _BACKOFF_SECONDS):
            if backoff:
                await asyncio.sleep(backoff)

            response = await client.post(url, auth=auth, data=data)
            logger.info("Twilio POST /Messages.json → %s", response.status_code)
            last_status_code = response.status_code

            if response.status_code in _RETRY_STATUSES:
                if attempt < len(_BACKOFF_SECONDS):
                    continue
                raise RuntimeError(f"Twilio failed after 3 retries: {last_status_code}")

            response.raise_for_status()
            return response.json()

    raise RuntimeError(f"Twilio failed after 3 retries: {last_status_code}")
