"""
ASGI middleware that stamps every HTTP request with a correlation ID,
populates ContextVars, and emits structured request start/end log lines.
"""
from __future__ import annotations

import logging
import time
from typing import Awaitable, Callable
from uuid import uuid4

logger = logging.getLogger(__name__)


class RequestContextMiddleware:
    """
    ASGI middleware — wraps every HTTP request/response cycle.

    Responsibilities:
    * Read or generate X-Request-ID.
    * Set correlation_id and route ContextVars.
    * Emit request.start / request.end / request.error log events.
    * Inject X-Request-ID into the response headers.
    """

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # ---- Import ContextVars (inside call to avoid circular imports) ----
        from app.observability.correlation import correlation_id, route as route_var

        # ---- Resolve request ID ----
        headers: dict[bytes, bytes] = {
            k.lower(): v for k, v in scope.get("headers", [])
        }
        raw_request_id = headers.get(b"x-request-id", b"")
        request_id = raw_request_id.decode() if raw_request_id else str(uuid4())

        # ---- Set ContextVars ----
        correlation_id.set(request_id)
        path: str = scope.get("path", "")
        route_var.set(path)

        method: str = scope.get("method", "")

        logger.info(
            "request.start",
            extra={"method": method, "path": path},
        )

        t0 = time.perf_counter()
        status_code: list[int] = []

        async def send_wrapper(message: dict) -> None:
            if message["type"] == "http.response.start":
                status_code.append(message["status"])
                # Inject X-Request-ID header into the response
                existing_headers: list[tuple[bytes, bytes]] = list(
                    message.get("headers", [])
                )
                existing_headers.append(
                    (b"x-request-id", request_id.encode())
                )
                message = {**message, "headers": existing_headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
            latency_ms = int((time.perf_counter() - t0) * 1000)
            logger.info(
                "request.end",
                extra={
                    "status": status_code[0] if status_code else None,
                    "latency_ms": latency_ms,
                    "correlation_id": request_id,
                },
            )
        except Exception:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            logger.error(
                "request.error",
                extra={
                    "method": method,
                    "path": path,
                    "latency_ms": latency_ms,
                    "correlation_id": request_id,
                },
                exc_info=True,
            )
            raise
