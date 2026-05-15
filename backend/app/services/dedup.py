from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func as _func

from app.models.contact import Contact
from app.models.invoice import Invoice
from integrations.ghl.models import ContactPayload, InvoicePayload


# ---------------------------------------------------------------------------
# Helper — server-side now() expression
# ---------------------------------------------------------------------------

def sa_now():
    return _func.now()


async def upsert_contact(session: AsyncSession, payload: ContactPayload) -> Contact:
    """Insert or update a Contact row, keyed on ghl_contact_id."""
    stmt = (
        insert(Contact)
        .values(
            ghl_contact_id=payload.ghl_contact_id,
            email=payload.email,
            phone=payload.phone,
            full_name=payload.full_name,
            organization_id=payload.organization_id,
        )
        .on_conflict_do_update(
            index_elements=["ghl_contact_id"],
            set_={
                "email": payload.email,
                "phone": payload.phone,
                "full_name": payload.full_name,
                "organization_id": payload.organization_id,
                "updated_at": sa_now(),
            },
        )
    )
    await session.execute(stmt)

    result = await session.execute(
        select(Contact).where(Contact.ghl_contact_id == payload.ghl_contact_id)
    )
    return result.scalar_one()


async def upsert_invoice(session: AsyncSession, payload: InvoicePayload) -> Invoice:
    """Insert or update an Invoice row, keyed on ghl_invoice_id."""
    # Resolve contact FK.
    contact_result = await session.execute(
        select(Contact).where(Contact.ghl_contact_id == payload.contact_ghl_id)
    )
    contact = contact_result.scalar_one_or_none()
    if contact is None:
        raise ValueError(f"Contact {payload.contact_ghl_id} not found")

    stmt = (
        insert(Invoice)
        .values(
            ghl_invoice_id=payload.ghl_invoice_id,
            contact_id=contact.id,
            amount=payload.amount,
            status=payload.status,
            payment_status=payload.payment_status,
            due_date=payload.due_date,
        )
        .on_conflict_do_update(
            index_elements=["ghl_invoice_id"],
            set_={
                "amount": payload.amount,
                "status": payload.status,
                "payment_status": payload.payment_status,
                "due_date": payload.due_date,
                "updated_at": sa_now(),
            },
        )
    )
    await session.execute(stmt)

    result = await session.execute(
        select(Invoice).where(Invoice.ghl_invoice_id == payload.ghl_invoice_id)
    )
    return result.scalar_one()
