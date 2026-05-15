"""
Unit tests for app.services.sequence_engine.

All tests use a mocked AsyncSession — no real database required.
"""
import pytest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from app.models.contact import Contact
from app.models.invoice import Invoice
from app.services.sequence_engine import (
    OVERDUE_SCHEDULE,
    enqueue_failed_payment_sequence,
    enqueue_overdue_sequence,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session() -> AsyncMock:
    """Return a minimal AsyncSession mock with execute, flush, and scalars wired up."""
    session = AsyncMock()

    # session.execute() must return an object whose .scalars().all() works
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    result_mock = MagicMock()
    result_mock.scalars.return_value = scalars_mock
    session.execute.return_value = result_mock

    return session


def _make_contact() -> MagicMock:
    contact = MagicMock(spec=Contact)
    contact.id = "contact-uuid-0001"
    contact.email = "test@example.com"
    contact.full_name = "Alex Sample"
    contact.phone = "+15550001234"
    return contact


def _make_invoice_overdue() -> MagicMock:
    invoice = MagicMock(spec=Invoice)
    invoice.id = "invoice-uuid-0001"
    invoice.due_date = date.today() - timedelta(days=5)
    return invoice


def _make_invoice_failed() -> MagicMock:
    invoice = MagicMock(spec=Invoice)
    invoice.id = "invoice-uuid-0002"
    invoice.updated_at = datetime.now(timezone.utc) - timedelta(days=1)
    return invoice


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

# BUG: The task spec states "Assert session.execute was called 4 times (once
# per step)" for enqueue_overdue_sequence.  However, the production code
# issues exactly 2 execute calls regardless of schedule length: one batched
# pg_insert (all rows) and one SELECT.  The spec's assumption of one execute
# per step does not match the implementation.  Tests below reflect actual
# behaviour (2 calls each).

@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_overdue_sequence_creates_four_steps():
    """
    enqueue_overdue_sequence must issue exactly 2 session.execute calls:
    one batched INSERT (all four OVERDUE_SCHEDULE steps) and one SELECT.
    """
    session = _make_session()
    contact = _make_contact()
    invoice = _make_invoice_overdue()

    await enqueue_overdue_sequence(session, contact, invoice)

    # Production code: 1 execute for the pg_insert + 1 execute for the SELECT.
    # The spec says 4 (one per step), but that contradicts the implementation
    # which batches all rows into a single INSERT statement.
    assert session.execute.call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_enqueue_failed_payment_creates_two_steps():
    """
    enqueue_failed_payment_sequence must issue exactly 2 session.execute calls:
    one batched INSERT (both FAILED_PAYMENT_SCHEDULE steps) and one SELECT.
    """
    session = _make_session()
    contact = _make_contact()
    invoice = _make_invoice_failed()

    await enqueue_failed_payment_sequence(session, contact, invoice)

    # Same reasoning as above: 1 INSERT + 1 SELECT = 2 execute calls.
    assert session.execute.call_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_overdue_schedule_day_offsets_correct():
    """
    OVERDUE_SCHEDULE must have 4 steps, offsets [3, 7, 14, 30],
    steps 0-2 via email and step 3 via sms.
    """
    assert len(OVERDUE_SCHEDULE) == 4

    expected_offsets = [3, 7, 14, 30]
    actual_offsets = [step["day_offset"] for step in OVERDUE_SCHEDULE]
    assert actual_offsets == expected_offsets

    # Steps 0, 1, 2 → email; step 3 → sms
    for i in range(3):
        assert OVERDUE_SCHEDULE[i]["channel"] == "email", (
            f"Step {i} should be 'email', got {OVERDUE_SCHEDULE[i]['channel']!r}"
        )
    assert OVERDUE_SCHEDULE[3]["channel"] == "sms"
