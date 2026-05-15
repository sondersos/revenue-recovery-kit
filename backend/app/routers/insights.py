"""
Insights router — commit() lives here, never inside services.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import CurrentUser, get_current_user
from app.core.database import get_db
from app.integrations.anthropic.client import AnthropicError
from app.models.detection import Insight
from app.schemas.insights import GenerateInsightRequest, InsightResponse
from app.services.insights.service import generate_insight

router = APIRouter(prefix="/v1/insights", tags=["insights"])


@router.get("/latest")
async def get_latest_insight(
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return the most recent Insight for this org, or 204 No Content."""
    org_id = _parse_org_id(current_user.organization_id)
    result = await session.execute(
        select(Insight)
        .where(Insight.organization_id == org_id)
        .order_by(Insight.generated_at.desc())
        .limit(1)
    )
    insight = result.scalar_one_or_none()
    if insight is None:
        return Response(status_code=204)

    return InsightResponse.model_validate(insight)


@router.post("", response_model=InsightResponse)
async def create_insight(
    body: GenerateInsightRequest,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
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


def _parse_org_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        return uuid.UUID("00000000-0000-0000-0000-000000000099")
