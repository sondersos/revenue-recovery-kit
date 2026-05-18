"""
Unit tests for app.services.dedup — upsert_contact and upsert_invoice.

Verifies that neither function calls session.commit() internally,
and that a missing contact causes ValueError without a commit.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from integrations.ghl.models import ContactPayload, InvoicePayload
from app.services.dedup import upsert_contact, upsert_invoice


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session() -> AsyncMock:
    """Return a minimal AsyncSession mock."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


def _make_fake_contact() -> MagicMock:
    from app.models.contact import Contact

    contact = MagicMock(spec=Contact)
    contact.id = "contact-uuid-0001"
    contact.ghl_contact_id = "cnt_test_001"
    contact.email = "test@example.com"
    contact.full_name = "Test User"
    return contact


def _make_fake_invoice() -> MagicMock:
    from app.models.invoice import Invoice

    invoice = MagicMock(spec=Invoice)
    invoice.id = "invoice-uuid-0001"
    invoice.ghl_invoice_id = "inv_test_001"
    return invoice


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upsert_contact_does_not_call_commit():
    """
    upsert_contact must NOT call session.commit() — the caller owns the
    transaction boundary.
    """
    session = _make_session()
    fake_contact = _make_fake_contact()

    # First execute: the INSERT ... ON CONFLICT (no return value needed).
    # Second execute: the SELECT — returns fake_contact via scalar_one().
    insert_result = MagicMock()
    select_result = MagicMock()
    select_result.scalar_one.return_value = fake_contact

    session.execute = AsyncMock(side_effect=[insert_result, select_result])

    payload = ContactPayload(
        ghl_contact_id="cnt_test_001",
        email="test@example.com",
        phone=None,
        full_name="Test User",
        organization_id=None,
    )

    result = await upsert_contact(session, payload)

    assert result is fake_contact
    assert (
        session.commit.call_count == 0
    ), f"upsert_contact called commit {session.commit.call_count} time(s); expected 0"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upsert_invoice_does_not_call_commit():
    """
    upsert_invoice must NOT call session.commit() — the caller owns the
    transaction boundary.
    """
    session = _make_session()
    fake_contact = _make_fake_contact()
    fake_invoice = _make_fake_invoice()

    # Execute call sequence:
    #   1. SELECT Contact for FK lookup  → scalar_one_or_none() = fake_contact
    #   2. INSERT ... ON CONFLICT        → no meaningful return
    #   3. SELECT Invoice post-upsert    → scalar_one() = fake_invoice

    contact_result = MagicMock()
    contact_result.scalar_one_or_none.return_value = fake_contact

    insert_result = MagicMock()

    invoice_result = MagicMock()
    invoice_result.scalar_one.return_value = fake_invoice

    session.execute = AsyncMock(
        side_effect=[contact_result, insert_result, invoice_result]
    )

    payload = InvoicePayload(
        ghl_invoice_id="inv_test_001",
        contact_ghl_id="cnt_test_001",
        amount=1500.00,
        status="overdue",
        payment_status="failed",
        due_date=None,
    )

    result = await upsert_invoice(session, payload)

    assert result is fake_invoice
    assert (
        session.commit.call_count == 0
    ), f"upsert_invoice called commit {session.commit.call_count} time(s); expected 0"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_upsert_invoice_raises_when_contact_missing():
    """
    upsert_invoice must raise ValueError containing 'not found' when the
    contact FK lookup returns None, and must NOT commit.
    """
    session = _make_session()

    # Only one execute call: SELECT Contact → returns None.
    contact_result = MagicMock()
    contact_result.scalar_one_or_none.return_value = None

    session.execute = AsyncMock(return_value=contact_result)

    payload = InvoicePayload(
        ghl_invoice_id="inv_test_001",
        contact_ghl_id="cnt_test_001",
        amount=1500.00,
        status="overdue",
        payment_status="failed",
        due_date=None,
    )

    with pytest.raises(ValueError, match="not found"):
        await upsert_invoice(session, payload)

    assert (
        session.commit.call_count == 0
    ), f"upsert_invoice called commit {session.commit.call_count} time(s) after raising; expected 0"
