import asyncio
import socket


async def probe_anthropic(timeout_s: float = 2.0) -> None:
    """Lightweight reachability check — no billable API call."""
    from app.core.config import settings

    if not settings.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not configured")

    loop = asyncio.get_running_loop()
    await asyncio.wait_for(
        loop.run_in_executor(
            None, lambda: socket.getaddrinfo("api.anthropic.com", 443)
        ),
        timeout=timeout_s,
    )
