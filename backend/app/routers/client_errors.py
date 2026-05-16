"""
POST /v1/client-errors — receive frontend error reports and emit structured log events.

Stacks are intentionally omitted from logs (too noisy for network timeouts).
"""
import logging

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["observability"])


class ClientErrorPayload(BaseModel):
    message: str
    stack: str | None = None
    route: str | None = None


@router.post("/client-errors")
@limiter.limit("5/minute")
async def report_client_error(request: Request, payload: ClientErrorPayload) -> Response:
    logger.warning(
        "client.error",
        extra={
            "client_message": payload.message[:500],
            "client_route": payload.route,
        },
    )
    # Stack intentionally excluded — noisy for network timeouts
    return Response(status_code=204)
