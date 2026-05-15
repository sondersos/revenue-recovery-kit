"""Unit tests for AnthropicAdapter — retry logic, sanitized logging, error handling."""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from anthropic import APIStatusError, APIConnectionError

from app.integrations.anthropic.client import AnthropicAdapter, AnthropicError, AnthropicResponse


def _make_message(text="ok", input_tokens=10, output_tokens=20, model="claude-test", stop_reason="end_turn"):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    msg.usage.input_tokens = input_tokens
    msg.usage.output_tokens = output_tokens
    msg.model = model
    msg.stop_reason = stop_reason
    return msg


def _make_status_error(status_code: int) -> APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = MagicMock()
    response.status_code = status_code
    response.request = request
    return APIStatusError(
        message=f"Error {status_code}",
        response=response,
        body=None,
    )


def _make_connection_error() -> APIConnectionError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return APIConnectionError(request=request)


_CALL_KWARGS = dict(
    system="sys",
    user="user input",
    model="claude-sonnet-4-5-20250929",
    max_tokens=800,
    temperature=0.2,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adapter_success_returns_response():
    adapter = AnthropicAdapter(api_key="test-key")
    msg = _make_message(text="Great insight.", input_tokens=50, output_tokens=100)

    with patch.object(adapter._client.messages, "create", new=AsyncMock(return_value=msg)):
        result = await adapter.complete(**_CALL_KWARGS)

    assert isinstance(result, AnthropicResponse)
    assert result.text == "Great insight."
    assert result.input_tokens == 50
    assert result.output_tokens == 100
    assert result.stop_reason == "end_turn"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adapter_retries_429_then_succeeds():
    adapter = AnthropicAdapter(api_key="test-key")
    msg = _make_message()
    err = _make_status_error(429)
    create_mock = AsyncMock(side_effect=[err, msg])

    with patch.object(adapter._client.messages, "create", new=create_mock):
        with patch("app.integrations.anthropic.client.asyncio.sleep", new=AsyncMock()):
            result = await adapter.complete(**_CALL_KWARGS)

    assert result.text == "ok"
    assert create_mock.call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adapter_retries_503_exhausted_raises_anthropic_error():
    adapter = AnthropicAdapter(api_key="test-key")
    err = _make_status_error(503)
    create_mock = AsyncMock(side_effect=[err, err, err, err])

    with patch.object(adapter._client.messages, "create", new=create_mock):
        with patch("app.integrations.anthropic.client.asyncio.sleep", new=AsyncMock()):
            with pytest.raises(AnthropicError):
                await adapter.complete(**_CALL_KWARGS)

    assert create_mock.call_count == 4  # 1 initial + 3 retries


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adapter_non_retryable_status_raises_immediately():
    adapter = AnthropicAdapter(api_key="test-key")
    err = _make_status_error(400)
    create_mock = AsyncMock(side_effect=err)

    with patch.object(adapter._client.messages, "create", new=create_mock):
        with pytest.raises(AnthropicError) as exc_info:
            await adapter.complete(**_CALL_KWARGS)

    assert create_mock.call_count == 1
    assert "400" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adapter_connection_error_retries_then_raises():
    adapter = AnthropicAdapter(api_key="test-key")
    conn_err = _make_connection_error()
    create_mock = AsyncMock(side_effect=[conn_err, conn_err, conn_err, conn_err])

    with patch.object(adapter._client.messages, "create", new=create_mock):
        with patch("app.integrations.anthropic.client.asyncio.sleep", new=AsyncMock()):
            with pytest.raises(AnthropicError):
                await adapter.complete(**_CALL_KWARGS)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_adapter_does_not_log_api_key_or_full_user(caplog):
    """Sanitized logging: only hash of first 64 chars, never the raw key or message."""
    import logging
    adapter = AnthropicAdapter(api_key="super-secret-key-12345")
    msg = _make_message()

    with patch.object(adapter._client.messages, "create", new=AsyncMock(return_value=msg)):
        with caplog.at_level(logging.INFO, logger="app.integrations.anthropic.client"):
            await adapter.complete(**_CALL_KWARGS)

    full_log = " ".join(caplog.messages)
    assert "super-secret-key-12345" not in full_log
    assert "user input" not in full_log
    assert "tokens_in" in full_log
