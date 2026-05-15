"""
FastAPI application entry-point for revenue-recovery-kit.

Architecture overview: docs/ARCHITECTURE.md
"""

from fastapi import FastAPI

app = FastAPI(
    title="revenue-recovery-kit",
    description="Automated revenue recovery for service agencies on Go High Level.",
    version="0.1.0",
)


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {"status": "ok", "service": "revenue-recovery-kit"}


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "healthy"}
