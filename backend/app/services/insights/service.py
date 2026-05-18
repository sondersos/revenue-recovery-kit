"""
Insights service — generate a Claude prose summary for a completed DetectionRun.

Transaction discipline: this module NEVER calls session.commit().
The caller (router layer) is responsible for committing.
"""

import json
import uuid
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.integrations.anthropic.client import AnthropicAdapter
from app.models.detection import Detection, DetectionRun, Insight
from app.services.insights.prompts import SYSTEM_PROMPT

# Anthropic pricing as of model snapshot (USD per 1M tokens)
_INPUT_COST_PER_M = Decimal("3.00")
_OUTPUT_COST_PER_M = Decimal("15.00")


def _compute_cost(input_tokens: int, output_tokens: int) -> Decimal:
    return (
        Decimal(input_tokens) / Decimal(1_000_000) * _INPUT_COST_PER_M
        + Decimal(output_tokens) / Decimal(1_000_000) * _OUTPUT_COST_PER_M
    ).quantize(Decimal("0.0001"))


async def generate_insight(
    session: AsyncSession,
    detection_run_id: uuid.UUID,
) -> Insight:
    """
    Load the DetectionRun + its Detections, build structured JSON input,
    call AnthropicAdapter.complete(), and persist the Insight row.

    Raises ValueError if the run does not exist or is not in 'complete' status.
    Raises AnthropicError on API failure.
    Caller is responsible for session.commit().
    """
    # 1. Load the detection run
    run_result = await session.execute(
        select(DetectionRun).where(DetectionRun.id == detection_run_id)
    )
    run = run_result.scalar_one_or_none()
    if run is None:
        raise ValueError(f"DetectionRun {detection_run_id} not found")
    if run.status != "complete":
        raise ValueError(
            f"DetectionRun {detection_run_id} status={run.status!r}, expected 'complete'"
        )

    # 2. Load its detections
    det_result = await session.execute(
        select(Detection).where(Detection.detection_run_id == detection_run_id)
    )
    detections = det_result.scalars().all()

    # 3. Build structured input payload
    by_rule: dict[str, list[dict]] = defaultdict(list)
    total_amount = Decimal("0")
    unique_contacts: set[str] = set()

    for det in detections:
        by_rule[det.rule_name].append(
            {
                "subject_id": str(det.subject_id),
                "severity": det.severity,
                "amount_usd": float(det.amount_usd) if det.amount_usd else None,
                "days_outstanding": det.days_outstanding,
                "recommended_action": det.recommended_action,
            }
        )
        if det.amount_usd:
            total_amount += det.amount_usd
        if det.subject_type == "contact":
            unique_contacts.add(str(det.subject_id))

    input_payload: dict = {
        "detection_run_id": str(detection_run_id),
        "organization_id": str(run.organization_id),
        "total_at_risk_usd": float(total_amount),
        "unique_contacts_flagged": len(unique_contacts),
        "total_detections": len(detections),
        "rule_counts": {rule: len(items) for rule, items in by_rule.items()},
        "detections_by_rule": dict(by_rule),
    }

    # 4. Call Claude
    adapter = AnthropicAdapter(api_key=settings.ANTHROPIC_API_KEY)
    response = await adapter.complete(
        system=SYSTEM_PROMPT,
        user=json.dumps(input_payload),
        model=settings.ANTHROPIC_MODEL,
        max_tokens=800,
        temperature=0.2,
    )

    # 5. Persist Insight row (caller commits)
    cost = _compute_cost(response.input_tokens, response.output_tokens)
    insight = Insight(
        detection_run_id=detection_run_id,
        organization_id=run.organization_id,
        input_payload=input_payload,
        summary_text=response.text,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=cost,
    )
    session.add(insight)

    return insight
