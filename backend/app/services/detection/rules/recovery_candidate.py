"""
Rule: recovery_candidate — Severity: HIGH

Invoice > 30 days unpaid (status != 'paid', created_at < now() - 30 days),
contact not in an active sequence (no sequence row with status='pending').
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, select

from app.models.detection import Detection
from app.models.invoice import Invoice
from app.models.sequence import Sequence
from app.services.detection.rules.base import Rule


class RecoveryCandidateRule(Rule):
    async def find(self, session, org_id: uuid.UUID) -> list:
        now = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(days=30)

        has_pending_sequence = exists(
            select(Sequence.id).where(
                Sequence.contact_id == Invoice.contact_id,
                Sequence.status == "pending",
            )
        )

        stmt = select(Invoice).where(
            Invoice.status != "paid",
            Invoice.created_at < cutoff,
            ~has_pending_sequence,
        )
        result = await session.execute(stmt)
        invoices = result.scalars().all()

        detections = []
        for inv in invoices:
            inv_created = inv.created_at
            if inv_created.tzinfo is None:
                inv_created = inv_created.replace(tzinfo=timezone.utc)
            days_out = (now - inv_created).days
            detections.append(
                Detection(
                    detection_run_id=None,
                    organization_id=org_id,
                    rule_name=self.name,
                    severity=self.severity,
                    subject_type=self.subject_type,
                    subject_id=inv.id,
                    amount_usd=inv.amount,
                    days_outstanding=days_out,
                    recommended_action=self.recommended_action,
                )
            )
        return detections


recovery_candidate_rule = RecoveryCandidateRule(
    name="recovery_candidate",
    description=(
        "Invoice more than 30 days unpaid and contact not enrolled "
        "in an active recovery sequence."
    ),
    severity="HIGH",
    subject_type="invoice",
    recommended_action=(
        "Enqueue recovery sequence immediately; "
        "consider direct founder call for amounts over $1,000."
    ),
)
