"""Drop duplicate named unique constraints on contacts and invoices.

Both tables have a named UniqueConstraint (uq_*) AND a unique index (ix_*)
covering the same column. The unique index alone enforces the constraint;
the named constraint is redundant and causes `alembic check` to report drift.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-15
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_contacts_ghl_contact_id", "contacts", type_="unique")
    op.drop_constraint("uq_invoices_ghl_invoice_id", "invoices", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_contacts_ghl_contact_id", "contacts", ["ghl_contact_id"]
    )
    op.create_unique_constraint(
        "uq_invoices_ghl_invoice_id", "invoices", ["ghl_invoice_id"]
    )
