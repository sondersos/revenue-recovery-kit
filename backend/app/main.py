"""
FastAPI application entry-point for revenue-recovery-kit.

Architecture overview: docs/ARCHITECTURE.md
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.middleware.rate_limit import limiter
from app.middleware.request_context import RequestContextMiddleware
from app.observability.logging import configure_logging
from app.routers.detection import router as detection_router
from app.routers.health import router as health_router
from app.routers.insights import router as insights_router
from app.routers.client_errors import router as client_errors_router
from app.worker import create_scheduler
from integrations.ghl.webhook import router as ghl_router

# Configure structured JSON logging before any other setup
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = create_scheduler(AsyncSessionLocal)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(
    title="revenue-recovery-kit",
    description="Automated revenue recovery for service agencies on Go High Level.",
    version="0.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# RequestContextMiddleware must be added LAST so it runs FIRST (ASGI stack is LIFO)
app.add_middleware(RequestContextMiddleware)

app.include_router(ghl_router)
app.include_router(detection_router)
app.include_router(insights_router)
app.include_router(client_errors_router)
app.include_router(health_router)


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {"status": "ok", "service": "revenue-recovery-kit"}
