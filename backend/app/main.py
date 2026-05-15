"""
FastAPI application entry-point for revenue-recovery-kit.

Architecture overview: docs/ARCHITECTURE.md
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.database import AsyncSessionLocal
from app.routers.detection import router as detection_router
from app.routers.insights import router as insights_router
from app.worker import create_scheduler
from integrations.ghl.webhook import router as ghl_router


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

app.include_router(ghl_router)
app.include_router(detection_router)
app.include_router(insights_router)


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {"status": "ok", "service": "revenue-recovery-kit"}


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "healthy"}
