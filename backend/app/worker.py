"""
APScheduler-based background worker.

Polls for due sequence steps every 60 seconds and dispatches
email / SMS messages via the relevant integration clients.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import sqlalchemy as sa
from app.models.contact import Contact
from app.services.sequence_engine import get_due_steps, mark_step_failed, mark_step_sent

logger = logging.getLogger(__name__)


async def execute_due_steps(sessionmaker: async_sessionmaker) -> None:
    """
    Fetch all pending sequence steps whose scheduled_at has passed,
    dispatch the appropriate channel message, and mark each step
    sent or failed.

    A per-step try/except ensures one failure never aborts the rest.
    """
    # Lazy-import integration clients so the worker module itself always
    # imports cleanly even when the integration packages are not yet wired up.
    from integrations.resend.client import send_recovery_email  # type: ignore[import]
    from integrations.twilio.client import send_recovery_sms    # type: ignore[import]

    async with sessionmaker() as session:
        due_steps = await get_due_steps(session)

        for step in due_steps:
            try:
                # Load the related Contact (needed for email address / phone number).
                result = await session.execute(
                    sa.select(Contact).where(Contact.id == step.contact_id)
                )
                contact = result.scalar_one_or_none()

                if contact is None:
                    logger.error(
                        "sequence_id=%s: contact %s not found — marking failed",
                        step.id,
                        step.contact_id,
                    )
                    await mark_step_failed(session, step.id)
                    continue

                recovery_message = (
                    f"Hi {contact.full_name or 'there'}, you have an outstanding "
                    "balance. Please contact us to resolve your account."
                )
                if step.channel == "email":
                    await send_recovery_email(
                        to_email=contact.email or "",
                        contact_name=contact.full_name or "",
                        message=recovery_message,
                    )
                elif step.channel == "sms":
                    await send_recovery_sms(
                        to_number=contact.phone or "",
                        message=recovery_message,
                    )
                else:
                    logger.warning(
                        "sequence_id=%s: unknown channel '%s' — skipping",
                        step.id,
                        step.channel,
                    )
                    continue

                await mark_step_sent(session, step.id)
                logger.info(
                    "sequence_id=%s channel=%s — sent", step.id, step.channel
                )

            except Exception:
                logger.exception(
                    "sequence_id=%s channel=%s — failed, marking as failed and continuing",
                    step.id,
                    step.channel,
                )
                try:
                    await mark_step_failed(session, step.id)
                except Exception:
                    logger.exception(
                        "sequence_id=%s — could not mark_step_failed", step.id
                    )

        await session.commit()


def create_scheduler(sessionmaker: async_sessionmaker) -> AsyncIOScheduler:
    """
    Build and return an AsyncIOScheduler that runs execute_due_steps
    every 60 seconds.

    Call scheduler.start() to begin and scheduler.shutdown() to stop.
    """
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        execute_due_steps,
        "interval",
        seconds=60,
        args=[sessionmaker],
        id="execute_due_steps",
        replace_existing=True,
    )
    return scheduler
