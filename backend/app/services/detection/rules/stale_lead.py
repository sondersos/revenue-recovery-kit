"""
Rule: stale_lead — Severity: MEDIUM

Contact created > 14 days ago, no invoice associated, no recent activity.
Approximation: contact.updated_at < now() - 14 days AND no invoices FK to this contact.
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import exists, select

from app.models.contact import Contact
from app.models.detection import Detection
from app.models.invoice import Invoice
from app.services.detection.rules.base import Rule


class StaleLeadRule(Rule):
    async def find(self, session, org_id: uuid.UUID) -> list:
        now = datetime.now(tz=timezone.utc)
        cutoff = now - timedelta(days=14)

        has_invoice = exists(
            select(Invoice.id).where(Invoice.contact_id == Contact.id)
        )

        stmt = select(Contact).where(
            Contact.updated_at < cutoff,
            ~has_invoice,
        )
        result = await session.execute(stmt)
        contacts = result.scalars().all()

        detections = []
        for contact in contacts:
            contact_created = contact.created_at
            if contact_created.tzinfo is None:
                contact_created = contact_created.replace(tzinfo=timezone.utc)
            days_out = (now - contact_created).days
            detections.append(
                Detection(
                    detection_run_id=None,
                    organization_id=org_id,
                    rule_name=self.name,
                    severity=self.severity,
                    subject_type=self.subject_type,
                    subject_id=contact.id,
                    amount_usd=None,
                    days_outstanding=days_out,
                    recommended_action=self.recommended_action,
                )
            )
        return detections


stale_lead_rule = StaleLeadRule(
    name="stale_lead",
    description=(
        "Contact created more than 14 days ago with no invoice ever issued "
        "and no recent activity."
    ),
    severity="MEDIUM",
    subject_type="contact",
    recommended_action=(
        "Re-engage contact with a value-add touchpoint; "
        "qualify for invoicing within 7 days."
    ),
)
