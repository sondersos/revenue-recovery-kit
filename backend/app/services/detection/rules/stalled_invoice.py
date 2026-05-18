"""
Rule: stalled_invoice — Severity: HIGH

Invoice issued > 7 days, status not 'paid', no activity logged in last 5 days.
Approximation (no separate activity log yet): invoice.updated_at < now() - 5 days
as a proxy for "no recent contact".
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.detection import Detection
from app.models.invoice import Invoice
from app.services.detection.rules.base import Rule


class StalledInvoiceRule(Rule):
    async def find(self, session, org_id: uuid.UUID) -> list:
        now = datetime.now(tz=timezone.utc)
        issued_cutoff = now - timedelta(days=7)
        activity_cutoff = now - timedelta(days=5)

        stmt = select(Invoice).where(
            Invoice.status != "paid",
            Invoice.created_at < issued_cutoff,
            Invoice.updated_at < activity_cutoff,
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
                    detection_run_id=None,  # set by engine after flush
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


stalled_invoice_rule = StalledInvoiceRule(
    name="stalled_invoice",
    description=(
        "Invoice issued more than 7 days ago, status not paid, "
        "and no activity in the last 5 days."
    ),
    severity="HIGH",
    subject_type="invoice",
    recommended_action=(
        "Send Day-7 overdue reminder via Resend; "
        "escalate to SMS if no reply within 48 hours."
    ),
)
