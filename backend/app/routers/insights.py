"""
Insights router — commit() lives here, never inside services.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import CurrentUser, get_current_user
from app.core.database import get_db
from app.integrations.anthropic.client import AnthropicError
from app.middleware.rate_limit import limiter
from app.models.detection import Insight
from app.schemas.insights import CostSummary, GenerateInsightRequest, InsightResponse
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
@limiter.limit("30/minute")
async def create_insight(
    request: Request,
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


@router.get("/cost-summary", response_model=CostSummary)
async def cost_summary(
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> CostSummary:
    """Return aggregated cost metrics for all insights in this org."""
    org_id = _parse_org_id(current_user.organization_id)

    # Aggregate cost, count, and earliest insight date for this org
    result = await session.execute(
        select(
            func.count(Insight.id),
            func.coalesce(func.sum(Insight.cost_usd), 0),
            func.min(Insight.generated_at),
        ).where(Insight.organization_id == org_id)
    )
    count, total_cost, since = result.one()

    # Per-model breakdown
    model_result = await session.execute(
        select(Insight.model, func.sum(Insight.cost_usd))
        .where(Insight.organization_id == org_id)
        .group_by(Insight.model)
    )
    by_model = {
        model: float(cost or 0)
        for model, cost in model_result.all()
    }

    avg = float(total_cost) / count if count > 0 else 0.0

    return CostSummary(
        total_cost_usd=float(total_cost),
        generation_count=count,
        avg_cost_usd=avg,
        since=since,
        by_model=by_model,
    )


def _parse_org_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        return uuid.UUID("00000000-0000-0000-0000-000000000099")
