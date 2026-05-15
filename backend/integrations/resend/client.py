import asyncio
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RETRY_STATUSES = {429, 500, 502, 503, 504}
_BACKOFF_SECONDS = [1, 2, 4]


async def send_recovery_email(to_email: str, contact_name: str, message: str) -> dict:
    """Send a recovery email via Resend with 3-retry exponential backoff.

    Does not log the API key, email body content, or contact PII beyond to_email.
    """
    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": "recovery@revenue-recovery-kit.dev",
        "to": [to_email],
        "subject": "Action required: outstanding balance",
        "text": message,
    }

    last_status_code: int | None = None

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt, backoff in enumerate([0] + _BACKOFF_SECONDS):
            if backoff:
                await asyncio.sleep(backoff)

            response = await client.post(url, headers=headers, json=payload)
            logger.info("Resend POST /emails → %s", response.status_code)
            last_status_code = response.status_code

            if response.status_code in _RETRY_STATUSES:
                if attempt < len(_BACKOFF_SECONDS):
                    continue
                raise RuntimeError(f"Resend failed after 3 retries: {last_status_code}")

            response.raise_for_status()
            return response.json()

    raise RuntimeError(f"Resend failed after 3 retries: {last_status_code}")
