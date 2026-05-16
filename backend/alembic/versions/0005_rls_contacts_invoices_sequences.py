"""Enable Row-Level Security on contacts, invoices, and sequences.

detection_runs, detections, and insights already have RLS from migration 0003.
This migration completes multi-tenant isolation for the remaining three tables.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-15
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE contacts ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY contacts_org_isolation ON contacts
            USING (organization_id = current_setting('app.current_org_id', TRUE));
        """
    )

    op.execute("ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY invoices_org_isolation ON invoices
            USING (
                contact_id IN (
                    SELECT id FROM contacts
                    WHERE organization_id = current_setting('app.current_org_id', TRUE)
                )
            );
        """
    )

    op.execute("ALTER TABLE sequences ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY sequences_org_isolation ON sequences
            USING (
                contact_id IN (
                    SELECT id FROM contacts
                    WHERE organization_id = current_setting('app.current_org_id', TRUE)
                )
            );
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS sequences_org_isolation ON sequences;")
    op.execute("ALTER TABLE sequences DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS invoices_org_isolation ON invoices;")
    op.execute("ALTER TABLE invoices DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS contacts_org_isolation ON contacts;")
    op.execute("ALTER TABLE contacts DISABLE ROW LEVEL SECURITY;")
