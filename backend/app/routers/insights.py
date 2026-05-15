"""
Insights router — commit() lives here, never inside services.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.integrations.anthropic.client import AnthropicError
from app.schemas.insights import GenerateInsightRequest, InsightResponse
from app.services.insights.service import generate_insight

router = APIRouter(prefix="/v1/insights", tags=["insights"])


@router.post("", response_model=InsightResponse)
async def create_insight(
    body: GenerateInsightRequest,
    session: AsyncSession = Depends(get_db),
) -> InsightResponse:
    """Generate a Claude prose insight for a completed DetectionRun."""
    try:
        insight = await generate_insight(session, body.detection_run_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AnthropicError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        await session.commit()
    except SQLAlchemyError as exc:
        await session.rollback()
        raise HTTPException(status_code=503, detail="Database error — please retry") from exc

    await session.refresh(insight)
    return InsightResponse.model_validate(insight)
