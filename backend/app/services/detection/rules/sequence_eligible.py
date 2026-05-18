"""
Rule: sequence_eligible — Severity: LOW

Broader catch-all: contact has a stalled or unpaid invoice OR is a stale lead,
AND has no active (pending) sequence.

"Stalled or unpaid invoice" = invoice.status != 'paid' AND invoice.created_at < now() - 7 days
"Stale lead" = contact.updated_at < now() - 14 days AND no invoice at all

This rule fires for contacts that match stalled_invoice OR stale_lead conditions
and are not already in a pending sequence.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, or_, select

from app.models.contact import Contact
from app.models.detection import Detection
from app.models.invoice import Invoice
from app.models.sequence import Sequence
from app.services.detection.rules.base import Rule


class SequenceEligibleRule(Rule):
    async def find(self, session, org_id: uuid.UUID) -> list:
        now = datetime.now(tz=timezone.utc)
        invoice_cutoff = now - timedelta(days=7)
        stale_cutoff = now - timedelta(days=14)

        # Stalled invoice condition: unpaid invoice older than 7 days
        has_stalled_invoice = exists(
            select(Invoice.id).where(
                Invoice.contact_id == Contact.id,
                Invoice.status != "paid",
                Invoice.created_at < invoice_cutoff,
            )
        )

        # Stale lead condition: no invoices at all and contact not updated in 14 days
        has_any_invoice = exists(
            select(Invoice.id).where(Invoice.contact_id == Contact.id)
        )

        is_stale_lead = Contact.updated_at < stale_cutoff

        # No active sequence
        has_pending_sequence = exists(
            select(Sequence.id).where(
                Sequence.contact_id == Contact.id,
                Sequence.status == "pending",
            )
        )

        stmt = select(Contact).where(
            or_(
                has_stalled_invoice,
                (is_stale_lead & ~has_any_invoice),
            ),
            ~has_pending_sequence,
        )
        result = await session.execute(stmt)
        contacts = result.scalars().all()

        detections = []
        for contact in contacts:
            detections.append(
                Detection(
                    detection_run_id=None,
                    organization_id=org_id,
                    rule_name=self.name,
                    severity=self.severity,
                    subject_type=self.subject_type,
                    subject_id=contact.id,
                    amount_usd=None,
                    days_outstanding=None,
                    recommended_action=self.recommended_action,
                )
            )
        return detections


sequence_eligible_rule = SequenceEligibleRule(
    name="sequence_eligible",
    description=(
        "Contact has a stalled or unpaid invoice or is a stale lead "
        "and is not enrolled in any active recovery sequence."
    ),
    severity="LOW",
    subject_type="contact",
    recommended_action=(
        "Automatically enqueue recovery sequence; no manual action required."
    ),
)
