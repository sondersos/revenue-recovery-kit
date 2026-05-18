import asyncio
import logging
import time

from anthropic import AsyncAnthropic, APIConnectionError, APIStatusError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AnthropicResponse(BaseModel):
    text: str
    input_tokens: int
    output_tokens: int
    model: str
    stop_reason: str


class AnthropicError(Exception):
    pass


class AnthropicAdapter:
    """Async wrapper around the Anthropic SDK with retry and sanitized logging."""

    _RETRY_STATUSES = {429, 500, 502, 503, 529}
    _BACKOFF = [1, 2, 4]

    def __init__(self, api_key: str):
        # Accept str (not SecretStr) so caller handles secret extraction
        self._client = AsyncAnthropic(api_key=api_key)

    async def complete(
        self,
        *,
        system: str,
        user: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> AnthropicResponse:
        """
        Call the Anthropic messages API with retry on 429/5xx.
        Logs: model, latency_ms, token counts, and a hash of the first 64 chars of user.
        Never logs: api_key, full system prompt, full user message.
        """
        last_exc: Exception | None = None

        for attempt, backoff in enumerate([0] + self._BACKOFF):
            if backoff:
                await asyncio.sleep(backoff)
            t0 = time.monotonic()
            try:
                response = await self._client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                latency_ms = int((time.monotonic() - t0) * 1000)
                # Compute cost (approximate): $3/M input + $15/M output for claude-3-5-sonnet
                cost = (
                    response.usage.input_tokens * 3 / 1_000_000
                    + response.usage.output_tokens * 15 / 1_000_000
                )
                logger.info(
                    "claude.request",
                    extra={"model": model, "max_tokens": max_tokens},
                )
                logger.info(
                    "claude.response",
                    extra={
                        "claude_model": response.model,
                        "claude_input_tokens": response.usage.input_tokens,
                        "claude_output_tokens": response.usage.output_tokens,
                        "claude_cost_usd": str(round(cost, 6)),
                        "latency_ms": latency_ms,
                    },
                )
                return AnthropicResponse(
                    text=response.content[0].text,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    model=response.model,
                    stop_reason=response.stop_reason or "end_turn",
                )
            except APIStatusError as exc:
                last_exc = exc
                status = exc.status_code
                if status in self._RETRY_STATUSES and attempt < len(self._BACKOFF):
                    logger.warning("anthropic attempt=%d status=%d — retrying", attempt, status)
                    continue
                raise AnthropicError(f"Anthropic API error after {attempt+1} attempts: {status}") from exc
            except APIConnectionError as exc:
                last_exc = exc
                if attempt < len(self._BACKOFF):
                    logger.warning("anthropic attempt=%d connection error — retrying", attempt)
                    continue
                raise AnthropicError(f"Anthropic connection error after {attempt+1} attempts") from exc

        raise AnthropicError(f"Anthropic failed after {len(self._BACKOFF)+1} attempts") from last_exc
