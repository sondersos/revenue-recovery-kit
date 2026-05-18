"""Create contacts and invoices tables

Revision ID: 0001
Revises: None
Create Date: 2026-05-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # contacts
    # ------------------------------------------------------------------
    op.create_table(
        "contacts",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("ghl_contact_id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("organization_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ghl_contact_id", name="uq_contacts_ghl_contact_id"),
    )
    op.create_index(
        "ix_contacts_ghl_contact_id",
        "contacts",
        ["ghl_contact_id"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # invoices
    # ------------------------------------------------------------------
    op.create_table(
        "invoices",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("ghl_invoice_id", sa.String(), nullable=False),
        sa.Column("contact_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("payment_status", sa.String(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"],
            ["contacts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ghl_invoice_id", name="uq_invoices_ghl_invoice_id"),
    )
    op.create_index(
        "ix_invoices_ghl_invoice_id",
        "invoices",
        ["ghl_invoice_id"],
        unique=True,
    )
    op.create_index(
        "ix_invoices_contact_id",
        "invoices",
        ["contact_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_invoices_contact_id", table_name="invoices")
    op.drop_index("ix_invoices_ghl_invoice_id", table_name="invoices")
    op.drop_table("invoices")
    op.drop_index("ix_contacts_ghl_contact_id", table_name="contacts")
    op.drop_table("contacts")
