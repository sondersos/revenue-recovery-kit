"""
Sequence engine: schedule and track outreach steps for overdue invoices
and failed payments.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.invoice import Invoice
from app.models.sequence import Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schedule definitions
# ---------------------------------------------------------------------------

OVERDUE_SCHEDULE: list[dict] = [
    {"step_index": 0, "day_offset": 3, "channel": "email"},
    {"step_index": 1, "day_offset": 7, "channel": "email"},
    {"step_index": 2, "day_offset": 14, "channel": "email"},
    {"step_index": 3, "day_offset": 30, "channel": "sms"},
]

FAILED_PAYMENT_SCHEDULE: list[dict] = [
    {"step_index": 0, "day_offset": 0, "channel": "email"},
    {"step_index": 1, "day_offset": 3, "channel": "sms"},
]


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def enqueue_overdue_sequence(
    session: AsyncSession,
    contact: Contact,
    invoice: Invoice,
) -> list[Sequence]:
    """
    Insert one Sequence row per step in OVERDUE_SCHEDULE.

    Idempotent: the INSERT ... ON CONFLICT DO NOTHING on the unique
    constraint (contact_id, sequence_type, step_index) means calling
    this twice for the same contact+invoice is safe.

    Returns the list of Sequence objects (fetched after upsert).
    """
    sequence_type = "overdue"

    # invoice.due_date is a date; convert to timezone-aware datetime at midnight UTC.
    if invoice.due_date is None:
        raise ValueError(
            f"Invoice {invoice.id} has no due_date — cannot schedule overdue sequence."
        )

    base_dt = datetime(
        invoice.due_date.year,
        invoice.due_date.month,
        invoice.due_date.day,
        tzinfo=timezone.utc,
    )

    rows = [
        {
            "contact_id": contact.id,
            "invoice_id": invoice.id,
            "sequence_type": sequence_type,
            "step_index": step["step_index"],
            "status": "pending",
            "channel": step["channel"],
            "scheduled_at": base_dt + timedelta(days=step["day_offset"]),
        }
        for step in OVERDUE_SCHEDULE
    ]

    stmt = (
        pg_insert(Sequence)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_sequences_contact_type_step")
    )
    await session.execute(stmt)
    await session.flush()

    result = await session.execute(
        sa.select(Sequence)
        .where(
            Sequence.contact_id == contact.id,
            Sequence.sequence_type == sequence_type,
            Sequence.invoice_id == invoice.id,
        )
        .order_by(Sequence.step_index)
    )
    return list(result.scalars().all())


async def enqueue_failed_payment_sequence(
    session: AsyncSession,
    contact: Contact,
    invoice: Invoice,
) -> list[Sequence]:
    """
    Insert one Sequence row per step in FAILED_PAYMENT_SCHEDULE.

    Idempotent via ON CONFLICT DO NOTHING.

    scheduled_at is based on invoice.updated_at (the time the payment failed).
    """
    sequence_type = "failed_payment"

    base_dt: datetime = invoice.updated_at
    if base_dt.tzinfo is None:
        base_dt = base_dt.replace(tzinfo=timezone.utc)

    rows = [
        {
            "contact_id": contact.id,
            "invoice_id": invoice.id,
            "sequence_type": sequence_type,
            "step_index": step["step_index"],
            "status": "pending",
            "channel": step["channel"],
            "scheduled_at": base_dt + timedelta(days=step["day_offset"]),
        }
        for step in FAILED_PAYMENT_SCHEDULE
    ]

    stmt = (
        pg_insert(Sequence)
        .values(rows)
        .on_conflict_do_nothing(constraint="uq_sequences_contact_type_step")
    )
    await session.execute(stmt)
    await session.flush()

    result = await session.execute(
        sa.select(Sequence)
        .where(
            Sequence.contact_id == contact.id,
            Sequence.sequence_type == sequence_type,
            Sequence.invoice_id == invoice.id,
        )
        .order_by(Sequence.step_index)
    )
    return list(result.scalars().all())


async def get_due_steps(session: AsyncSession) -> list[Sequence]:
    """
    Return all Sequence rows where status='pending' and scheduled_at <= now(),
    ordered by scheduled_at ascending.
    """
    now = datetime.now(tz=timezone.utc)
    result = await session.execute(
        sa.select(Sequence)
        .where(
            Sequence.status == "pending",
            Sequence.scheduled_at <= now,
        )
        .order_by(Sequence.scheduled_at.asc())
    )
    return list(result.scalars().all())


async def mark_step_sent(session: AsyncSession, sequence_id: uuid.UUID) -> None:
    """Mark a Sequence step as sent and record the execution timestamp."""
    now = datetime.now(tz=timezone.utc)
    await session.execute(
        sa.update(Sequence)
        .where(Sequence.id == sequence_id)
        .values(status="sent", executed_at=now)
    )


async def mark_step_failed(session: AsyncSession, sequence_id: uuid.UUID) -> None:
    """Mark a Sequence step as failed and record the execution timestamp."""
    now = datetime.now(tz=timezone.utc)
    await session.execute(
        sa.update(Sequence)
        .where(Sequence.id == sequence_id)
        .values(status="failed", executed_at=now)
    )
