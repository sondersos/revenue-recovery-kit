"""
Seed the local database with 1k contacts and 1k invoices for load testing.

Usage:
    docker compose exec api python scripts/seed.py
    docker compose exec api python scripts/seed.py --org <uuid>  # specific org
    docker compose exec api python scripts/seed.py --clear        # clear first
"""

import argparse
import asyncio
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.models.contact import Contact
from app.models.invoice import Invoice

SEED_ORG_ID = "00000000-0000-0000-0000-000000000001"
N_CONTACTS = 1000
N_INVOICES = 1000

STATUSES = ["draft", "sent", "overdue", "overdue", "overdue", "paid"]
CHANNELS = ["email", "sms"]


def _random_date(days_ago_min: int, days_ago_max: int) -> datetime:
    days = random.randint(days_ago_min, days_ago_max)
    return datetime.now(tz=timezone.utc) - timedelta(days=days)


async def seed(org_id: str, clear: bool = False) -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL not set")

    engine = create_async_engine(url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        if clear:
            print("Clearing existing data for org…")
            from sqlalchemy import delete
            await session.execute(
                delete(Invoice).where(
                    Invoice.contact_id.in_(
                        __import__("sqlalchemy").select(Contact.id).where(
                            Contact.organization_id == org_id
                        ).scalar_subquery()
                    )
                )
            )
            await session.execute(
                delete(Contact).where(Contact.organization_id == org_id)
            )
            await session.commit()
            print("  done.")

        print(f"Seeding {N_CONTACTS} contacts…")
        contacts = []
        for i in range(N_CONTACTS):
            c = Contact(
                id=uuid.uuid4(),
                ghl_contact_id=f"ghl-seed-{uuid.uuid4().hex[:12]}",
                email=f"seed{i}@example.com",
                phone=f"+1555{i:07d}",
                full_name=f"Seed Contact {i}",
                organization_id=org_id,
                created_at=_random_date(1, 90),
                updated_at=_random_date(1, 60),
            )
            contacts.append(c)
        session.add_all(contacts)
        await session.flush()
        print(f"  inserted {len(contacts)} contacts.")

        print(f"Seeding {N_INVOICES} invoices…")
        invoices = []
        for i in range(N_INVOICES):
            contact = contacts[i % len(contacts)]
            status = random.choice(STATUSES)
            created = _random_date(5, 120)
            inv = Invoice(
                id=uuid.uuid4(),
                ghl_invoice_id=f"inv-seed-{uuid.uuid4().hex[:12]}",
                contact_id=contact.id,
                amount=round(random.uniform(50, 5000), 2),
                status=status,
                payment_status="failed" if status != "paid" else "paid",
                due_date=(created + timedelta(days=30)).date(),
                created_at=created,
                updated_at=_random_date(1, 30),
            )
            invoices.append(inv)
        session.add_all(invoices)
        await session.commit()
        print(f"  inserted {len(invoices)} invoices.")

    await engine.dispose()
    print(f"\nSeed complete. Org: {org_id}")
    print(f"  {N_CONTACTS} contacts, {N_INVOICES} invoices")
    unpaid = sum(1 for inv in invoices if inv.status != "paid")
    print(f"  {unpaid} unpaid invoices (detection rules will fire on these)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default=SEED_ORG_ID)
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args()
    asyncio.run(seed(args.org, args.clear))
