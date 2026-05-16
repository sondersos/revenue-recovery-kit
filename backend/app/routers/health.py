from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.integrations.anthropic.probe import probe_anthropic

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health() -> dict:
    return {"status": "healthy"}


@router.get("/healthz")
async def healthz(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    checks: dict[str, str] = {}

    # DB probe
    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"fail: {type(exc).__name__}"

    # Anthropic probe (lightweight — just verify key set + DNS resolves)
    try:
        await probe_anthropic(timeout_s=2)
        checks["anthropic"] = "ok"
    except Exception as exc:
        checks["anthropic"] = f"fail: {type(exc).__name__}"

    all_ok = all(v == "ok" for v in checks.values())
    status_code = 200 if all_ok else 503
    return JSONResponse(
        {"status": "ok" if all_ok else "degraded", "checks": checks},
        status_code=status_code,
    )
