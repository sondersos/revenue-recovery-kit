"""
Detection router — commit() lives here, never inside services.
"""
import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.detection import Detection, DetectionRun
from app.schemas.detection import (
    DetectionItem,
    DetectionRunDetail,
    DetectionSummary,
    RunDetectionRequest,
)
from app.services.detection.engine import run_detection

router = APIRouter(prefix="/v1/detection", tags=["detection"])

# Placeholder org_id until real auth is wired on Day 5
_DEFAULT_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000099")


@router.post("/run", response_model=DetectionSummary)
async def trigger_detection_run(
    body: RunDetectionRequest,
    session: AsyncSession = Depends(get_db),
) -> DetectionSummary:
    """Run all detection rules and persist the results."""
    org_id = _DEFAULT_ORG_ID
    try:
        run = await run_detection(session, org_id, body.window_days)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Load detections to build summary counts
    result = await session.execute(
        select(Detection).where(Detection.detection_run_id == run.id)
    )
    detections = result.scalars().all()

    counts: dict[str, int] = defaultdict(int)
    total_at_risk = Decimal("0")
    for det in detections:
        counts[det.rule_name] += 1
        if det.amount_usd is not None:
            total_at_risk += det.amount_usd

    return DetectionSummary(
        detection_run_id=run.id,
        status=run.status,
        counts=dict(counts),
        total_at_risk_usd=float(total_at_risk),
        detection_count=run.detection_count,
    )


@router.get("/runs/{run_id}", response_model=DetectionRunDetail)
async def get_detection_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> DetectionRunDetail:
    """Fetch a detection run and its detections grouped by rule name."""
    run_result = await session.execute(
        select(DetectionRun).where(DetectionRun.id == run_id)
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Detection run not found")

    det_result = await session.execute(
        select(Detection).where(Detection.detection_run_id == run_id)
    )
    detections = det_result.scalars().all()

    grouped: dict[str, list[DetectionItem]] = defaultdict(list)
    for det in detections:
        grouped[det.rule_name].append(
            DetectionItem(
                id=det.id,
                rule_name=det.rule_name,
                severity=det.severity,
                subject_type=det.subject_type,
                subject_id=det.subject_id,
                amount_usd=float(det.amount_usd) if det.amount_usd is not None else None,
                days_outstanding=det.days_outstanding,
                recommended_action=det.recommended_action,
            )
        )

    return DetectionRunDetail(
        id=run.id,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        rule_count=run.rule_count,
        detection_count=run.detection_count,
        detections=dict(grouped),
    )
