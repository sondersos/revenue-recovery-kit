from datetime import date, datetime, timedelta, timezone

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.invoice import Invoice


async def get_at_risk_contacts(session: AsyncSession) -> list[Contact]:
    """Return distinct contacts that have at least one overdue or recently-failed invoice.

    Rule A (overdue):
        invoice.status != 'paid' AND invoice.due_date < today

    Rule B (failed payment, recent):
        invoice.payment_status == 'failed' AND invoice.updated_at > now() - 30 days
    """
    today = date.today()
    thirty_days_ago = datetime.now(tz=timezone.utc) - timedelta(days=30)

    overdue_exists = exists(
        select(Invoice.id).where(
            Invoice.contact_id == Contact.id,
            Invoice.status != "paid",
            Invoice.due_date < today,
        )
    )

    failed_payment_exists = exists(
        select(Invoice.id).where(
            Invoice.contact_id == Contact.id,
            Invoice.payment_status == "failed",
            Invoice.updated_at > thirty_days_ago,
        )
    )

    stmt = select(Contact).where(or_(overdue_exists, failed_payment_exists)).distinct()

    result = await session.execute(stmt)
    return list(result.scalars().all())
