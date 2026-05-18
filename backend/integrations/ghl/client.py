import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)

_RETRY_STATUSES = {429, 500, 502, 503, 504}
_BACKOFF_SECONDS = [1, 2, 4]


class GHLClient:
    """Async HTTP client for the GoHighLevel REST API."""

    BASE_URL = "https://services.leadconnectorhq.com"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=10.0,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    async def get_contact(self, contact_id: str) -> dict:
        """Fetch a single GHL contact by ID with 3-retry exponential backoff."""
        path = f"/contacts/{contact_id}"
        last_exc: Exception | None = None

        for attempt, backoff in enumerate([0] + _BACKOFF_SECONDS):
            if backoff:
                await asyncio.sleep(backoff)
            try:
                response = await self._client.get(path)
                logger.info(
                    "GHL GET /contacts/%s → %s", contact_id, response.status_code
                )
                if response.status_code in _RETRY_STATUSES and attempt < len(
                    _BACKOFF_SECONDS
                ):
                    last_exc = httpx.HTTPStatusError(
                        f"Retryable status {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code not in _RETRY_STATUSES:
                    raise
                if attempt >= len(_BACKOFF_SECONDS):
                    raise
            except httpx.RequestError as exc:
                last_exc = exc
                if attempt >= len(_BACKOFF_SECONDS):
                    raise

        raise last_exc  # type: ignore[misc]

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "GHLClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()
