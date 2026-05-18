"""
Detection engine — iterates REGISTRY, collects Detection rows, bulk-inserts.

Transaction discipline: this module NEVER calls session.commit().
The caller (router layer) is responsible for committing or rolling back.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.detection import Detection, DetectionRun
from app.services.detection.rules import REGISTRY


async def run_detection(
    session: AsyncSession,
    org_id: uuid.UUID,
    window_days: int = 30,
) -> DetectionRun:
    """
    Create a detection run, execute all rules, bulk-insert detections, update run status.

    Caller is responsible for session.commit().
    On exception: set run.status='failed', run.error_message=str(e), re-raise.
    Do NOT commit detections on failure.
    """
    # 1. Create DetectionRun row (status='running'), flush to get id
    run = DetectionRun(
        organization_id=org_id,
        status="running",
        rule_count=0,
        detection_count=0,
    )
    session.add(run)
    await session.flush()  # assigns run.id via server default

    try:
        # 2. Run each rule in REGISTRY, collect Detection objects
        all_detections: list[Detection] = []
        for rule in REGISTRY:
            rule_detections = await rule.find(session, org_id)
            # Assign the detection_run_id now that we have it
            for det in rule_detections:
                det.detection_run_id = run.id
            all_detections.extend(rule_detections)

        # 3. Bulk insert all detections
        if all_detections:
            session.add_all(all_detections)

        # 4. Update run: finished_at=now(), status='complete', rule_count, detection_count
        run.finished_at = datetime.now(tz=timezone.utc)
        run.status = "complete"
        run.rule_count = len(REGISTRY)
        run.detection_count = len(all_detections)

        # 5. Return the DetectionRun object (caller commits)
        return run

    except Exception as exc:
        # On exception: update run status, do NOT commit detections
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = datetime.now(tz=timezone.utc)
        raise
