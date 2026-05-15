"""
Detection router — commit() lives here, never inside services.
"""
import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import CurrentUser, get_current_user
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


@router.post("/run", response_model=DetectionSummary)
async def trigger_detection_run(
    body: RunDetectionRequest,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DetectionSummary:
    """Run all detection rules and persist the results."""
    org_id = uuid.UUID(current_user.organization_id) if _is_valid_uuid(current_user.organization_id) else uuid.UUID("00000000-0000-0000-0000-000000000099")
    try:
        run = await run_detection(session, org_id, body.window_days)
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

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


@router.get("/runs/latest")
async def get_latest_detection_run(
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return the most recent DetectionRun for this org, or 204."""
    org_id = _parse_org_id(current_user.organization_id)
    result = await session.execute(
        select(DetectionRun)
        .where(DetectionRun.organization_id == org_id)
        .order_by(DetectionRun.started_at.desc())
        .limit(1)
    )
    run = result.scalar_one_or_none()
    if run is None:
        from fastapi.responses import Response
        return Response(status_code=204)

    return {
        "id": str(run.id),
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "status": run.status,
        "rule_count": run.rule_count,
        "detection_count": run.detection_count,
    }


@router.get("/runs/{run_id}", response_model=DetectionRunDetail)
async def get_detection_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> DetectionRunDetail:
    """Fetch a detection run and its detections grouped by rule name."""
    org_id = _parse_org_id(current_user.organization_id)
    run_result = await session.execute(
        select(DetectionRun).where(
            DetectionRun.id == run_id,
            DetectionRun.organization_id == org_id,
        )
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


@router.get("/runs/{run_id}/detections", response_model=list[DetectionItem])
async def list_detections(
    run_id: uuid.UUID,
    limit: int = 10,
    session: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[DetectionItem]:
    """Flat list of detections for a run, sorted by amount_usd desc."""
    import sqlalchemy as sa

    org_id = _parse_org_id(current_user.organization_id)
    run_result = await session.execute(
        select(DetectionRun).where(
            DetectionRun.id == run_id,
            DetectionRun.organization_id == org_id,
        )
    )
    if run_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Detection run not found")

    det_result = await session.execute(
        select(Detection)
        .where(Detection.detection_run_id == run_id)
        .order_by(sa.nulls_last(Detection.amount_usd.desc()))
        .limit(limit)
    )
    detections = det_result.scalars().all()
    return [
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
        for det in detections
    ]


def _is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


def _parse_org_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        return uuid.UUID("00000000-0000-0000-0000-000000000099")
