"""
Unit tests for detection rules — each rule's find() method.
Sessions are mocked; no real database I/O.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.detection.rules.stalled_invoice import stalled_invoice_rule
from app.services.detection.rules.stale_lead import stale_lead_rule
from app.services.detection.rules.recovery_candidate import recovery_candidate_rule
from app.services.detection.rules.sequence_eligible import sequence_eligible_rule


ORG_ID = uuid.uuid4()
NOW = datetime.now(tz=timezone.utc)


def _mock_session(rows: list):
    """Return a mock AsyncSession whose execute() yields the given rows."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    return session


def _invoice(
    *,
    id: uuid.UUID | None = None,
    status: str = "sent",
    amount: Decimal = Decimal("500.00"),
    days_old: int = 10,
    days_since_update: int = 6,
    contact_id: uuid.UUID | None = None,
) -> MagicMock:
    inv = MagicMock()
    inv.id = id or uuid.uuid4()
    inv.status = status
    inv.amount = amount
    inv.contact_id = contact_id or uuid.uuid4()
    inv.created_at = NOW - timedelta(days=days_old)
    inv.updated_at = NOW - timedelta(days=days_since_update)
    return inv


def _contact(
    *,
    id: uuid.UUID | None = None,
    days_old: int = 20,
    days_since_update: int = 20,
) -> MagicMock:
    c = MagicMock()
    c.id = id or uuid.uuid4()
    c.created_at = NOW - timedelta(days=days_old)
    c.updated_at = NOW - timedelta(days=days_since_update)
    return c


# ---------------------------------------------------------------------------
# stalled_invoice_rule
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_stalled_invoice_finds_overdue_invoices():
    inv = _invoice(days_old=10, days_since_update=6, status="sent")
    session = _mock_session([inv])

    detections = await stalled_invoice_rule.find(session, ORG_ID)

    assert len(detections) == 1
    det = detections[0]
    assert det.rule_name == "stalled_invoice"
    assert det.severity == "HIGH"
    assert det.subject_type == "invoice"
    assert det.subject_id == inv.id
    assert det.amount_usd == inv.amount
    assert det.days_outstanding >= 10


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stalled_invoice_returns_empty_when_no_rows():
    session = _mock_session([])
    detections = await stalled_invoice_rule.find(session, ORG_ID)
    assert detections == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stalled_invoice_detection_run_id_is_none():
    """Engine must set detection_run_id after flush — rule leaves it None."""
    inv = _invoice()
    session = _mock_session([inv])
    detections = await stalled_invoice_rule.find(session, ORG_ID)
    assert detections[0].detection_run_id is None


# ---------------------------------------------------------------------------
# stale_lead_rule
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_stale_lead_finds_contacts_without_invoice():
    contact = _contact(days_old=20, days_since_update=20)
    session = _mock_session([contact])

    detections = await stale_lead_rule.find(session, ORG_ID)

    assert len(detections) == 1
    det = detections[0]
    assert det.rule_name == "stale_lead"
    assert det.severity == "MEDIUM"
    assert det.subject_type == "contact"
    assert det.subject_id == contact.id
    assert det.amount_usd is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stale_lead_returns_empty_when_no_rows():
    session = _mock_session([])
    detections = await stale_lead_rule.find(session, ORG_ID)
    assert detections == []


# ---------------------------------------------------------------------------
# recovery_candidate_rule
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_recovery_candidate_finds_31_day_unpaid_invoice():
    inv = _invoice(days_old=31, status="sent", amount=Decimal("1200.00"))
    session = _mock_session([inv])

    detections = await recovery_candidate_rule.find(session, ORG_ID)

    assert len(detections) == 1
    det = detections[0]
    assert det.rule_name == "recovery_candidate"
    assert det.severity == "HIGH"
    assert det.amount_usd == Decimal("1200.00")
    assert det.days_outstanding >= 31


@pytest.mark.unit
@pytest.mark.asyncio
async def test_recovery_candidate_recommended_action_mentions_enqueue():
    inv = _invoice(days_old=35)
    session = _mock_session([inv])
    detections = await recovery_candidate_rule.find(session, ORG_ID)
    assert "sequence" in detections[0].recommended_action.lower()


# ---------------------------------------------------------------------------
# sequence_eligible_rule
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_sequence_eligible_returns_contacts():
    contact = _contact(days_old=20)
    session = _mock_session([contact])

    detections = await sequence_eligible_rule.find(session, ORG_ID)

    assert len(detections) == 1
    det = detections[0]
    assert det.rule_name == "sequence_eligible"
    assert det.severity == "LOW"
    assert det.subject_type == "contact"
    assert det.amount_usd is None
    assert det.days_outstanding is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sequence_eligible_organization_id_matches():
    contact = _contact()
    session = _mock_session([contact])
    detections = await sequence_eligible_rule.find(session, ORG_ID)
    assert detections[0].organization_id == ORG_ID
