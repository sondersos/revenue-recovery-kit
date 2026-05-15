"""
Unit tests for app.worker.execute_due_steps — atomicity and per-step savepoints.

Verifies that:
  - A successful step is marked sent and the session is committed.
  - A failed send is marked failed but the session is still committed.
  - Two steps are independent: one failure does not prevent the other from
    being marked correctly.
  - A missing contact causes mark_step_failed without any send attempt.

No real database or HTTP connections are used.
"""
import uuid
from typing import Optional
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.worker import execute_due_steps


# ---------------------------------------------------------------------------
# Helper: build a consistent mock session
# ---------------------------------------------------------------------------

def make_mock_session() -> AsyncMock:
    """
    Build a mock AsyncSession that supports:
      - execute()       — returns a result with scalar_one_or_none()
      - begin_nested()  — returns a proper async context manager (savepoint)
      - commit()        — AsyncMock
      - rollback()      — AsyncMock
    """
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    # begin_nested() must return an async context manager.
    nested_cm = MagicMock()
    nested_cm.__aenter__ = AsyncMock(return_value=None)
    nested_cm.__aexit__ = AsyncMock(return_value=False)  # False → don't suppress exceptions
    session.begin_nested = MagicMock(return_value=nested_cm)

    return session


def make_mock_step(
    step_id: Optional[uuid.UUID] = None,
    channel: str = "email",
    contact_id: Optional[uuid.UUID] = None,
) -> MagicMock:
    """Return a minimal Sequence-like mock."""
    step = MagicMock()
    step.id = step_id or uuid.uuid4()
    step.channel = channel
    step.contact_id = contact_id or uuid.uuid4()
    return step


def make_mock_contact(step: MagicMock) -> MagicMock:
    """Return a Contact-like mock whose id matches the step's contact_id."""
    contact = MagicMock()
    contact.id = step.contact_id
    contact.email = "test@example.com"
    contact.full_name = "Test User"
    contact.phone = "+15550001234"
    return contact


def _make_sessionmaker(session: AsyncMock):
    """
    Return a callable that acts as an async_sessionmaker:
      async with sessionmaker() as session: ...
    """
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    sessionmaker = MagicMock(return_value=cm)
    return sessionmaker


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_marks_step_sent_on_success():
    """
    One pending email step, contact found, send succeeds →
    mark_step_sent called once, mark_step_failed not called,
    session.commit called once.
    """
    session = make_mock_session()
    step = make_mock_step(channel="email")
    contact = make_mock_contact(step)

    contact_result = MagicMock()
    contact_result.scalar_one_or_none.return_value = contact
    session.execute = AsyncMock(return_value=contact_result)

    sessionmaker = _make_sessionmaker(session)

    with (
        patch("app.worker.get_due_steps", new_callable=AsyncMock) as mock_due,
        patch("app.worker.mark_step_sent", new_callable=AsyncMock) as mock_sent,
        patch("app.worker.mark_step_failed", new_callable=AsyncMock) as mock_failed,
        patch("integrations.resend.client.send_recovery_email", new_callable=AsyncMock) as mock_email,
        patch("integrations.twilio.client.send_recovery_sms", new_callable=AsyncMock) as mock_sms,
    ):
        mock_due.return_value = [step]
        mock_email.return_value = {"id": "email-id-001"}

        await execute_due_steps(sessionmaker)

    mock_sent.assert_called_once_with(session, step.id)
    mock_failed.assert_not_called()
    session.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_marks_step_failed_on_send_error():
    """
    One pending email step, contact found, send_recovery_email raises →
    mark_step_failed called once, mark_step_sent not called,
    session.commit still called once (batch commits regardless).
    """
    session = make_mock_session()
    step = make_mock_step(channel="email")
    contact = make_mock_contact(step)

    contact_result = MagicMock()
    contact_result.scalar_one_or_none.return_value = contact
    session.execute = AsyncMock(return_value=contact_result)

    # begin_nested()'s __aexit__ must propagate the exception (return False).
    # The outer except in execute_due_steps catches it and opens a second
    # begin_nested() to call mark_step_failed.
    sessionmaker = _make_sessionmaker(session)

    with (
        patch("app.worker.get_due_steps", new_callable=AsyncMock) as mock_due,
        patch("app.worker.mark_step_sent", new_callable=AsyncMock) as mock_sent,
        patch("app.worker.mark_step_failed", new_callable=AsyncMock) as mock_failed,
        patch("integrations.resend.client.send_recovery_email", new_callable=AsyncMock) as mock_email,
        patch("integrations.twilio.client.send_recovery_sms", new_callable=AsyncMock) as mock_sms,
    ):
        mock_due.return_value = [step]
        mock_email.side_effect = RuntimeError("send failed")

        await execute_due_steps(sessionmaker)

    mock_failed.assert_called_once_with(session, step.id)
    mock_sent.assert_not_called()
    session.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_continues_after_one_step_fails():
    """
    Two pending steps: step_a (email, succeeds) and step_b (sms, raises) →
    mark_step_sent called once (step_a), mark_step_failed called once (step_b),
    session.commit called once at the end.
    """
    session = make_mock_session()

    step_a = make_mock_step(channel="email")
    step_b = make_mock_step(channel="sms")

    contact_a = make_mock_contact(step_a)
    contact_b = make_mock_contact(step_b)

    # execute() is called once per step (contact lookup), alternating contacts.
    result_a = MagicMock()
    result_a.scalar_one_or_none.return_value = contact_a

    result_b = MagicMock()
    result_b.scalar_one_or_none.return_value = contact_b

    session.execute = AsyncMock(side_effect=[result_a, result_b])

    sessionmaker = _make_sessionmaker(session)

    with (
        patch("app.worker.get_due_steps", new_callable=AsyncMock) as mock_due,
        patch("app.worker.mark_step_sent", new_callable=AsyncMock) as mock_sent,
        patch("app.worker.mark_step_failed", new_callable=AsyncMock) as mock_failed,
        patch("integrations.resend.client.send_recovery_email", new_callable=AsyncMock) as mock_email,
        patch("integrations.twilio.client.send_recovery_sms", new_callable=AsyncMock) as mock_sms,
    ):
        mock_due.return_value = [step_a, step_b]
        mock_email.return_value = {"id": "email-id-001"}
        mock_sms.side_effect = RuntimeError("sms failed")

        await execute_due_steps(sessionmaker)

    mock_sent.assert_called_once_with(session, step_a.id)
    mock_failed.assert_called_once_with(session, step_b.id)
    session.commit.assert_called_once()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_worker_marks_failed_when_contact_missing():
    """
    One pending step, contact lookup returns None →
    mark_step_failed called once, send_recovery_email and
    send_recovery_sms NOT called.
    """
    session = make_mock_session()
    step = make_mock_step(channel="email")

    missing_result = MagicMock()
    missing_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=missing_result)

    sessionmaker = _make_sessionmaker(session)

    with (
        patch("app.worker.get_due_steps", new_callable=AsyncMock) as mock_due,
        patch("app.worker.mark_step_sent", new_callable=AsyncMock) as mock_sent,
        patch("app.worker.mark_step_failed", new_callable=AsyncMock) as mock_failed,
        patch("integrations.resend.client.send_recovery_email", new_callable=AsyncMock) as mock_email,
        patch("integrations.twilio.client.send_recovery_sms", new_callable=AsyncMock) as mock_sms,
    ):
        mock_due.return_value = [step]

        await execute_due_steps(sessionmaker)

    mock_failed.assert_called_once_with(session, step.id)
    mock_sent.assert_not_called()
    mock_email.assert_not_called()
    mock_sms.assert_not_called()
