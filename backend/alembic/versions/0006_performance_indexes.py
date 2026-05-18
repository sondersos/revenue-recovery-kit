"""Add performance indexes for hot-path dashboard queries.

All indexes use CREATE INDEX CONCURRENTLY which cannot run inside a
transaction block. We open a SECOND connection in AUTOCOMMIT mode for
the DDL so the original migration connection (which handles the
alembic_version update) remains in its normal transaction.

See ADR-0008 for the full rationale.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_UPGRADE_SQLS = [
    # Powers GET /v1/detection/runs/latest — most-recent run per org in O(log n).
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
    "idx_detection_runs_org_started "
    "ON detection_runs(organization_id, started_at DESC)",
    # Powers GET /v1/insights/latest — most-recent insight per org in O(log n).
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
    "idx_insights_org_generated "
    "ON insights(organization_id, generated_at DESC)",
    # Powers /runs/{id}/detections listing sorted by amount (top-10 table).
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
    "idx_detections_run_amount "
    "ON detections(detection_run_id, amount_usd DESC NULLS LAST)",
    # Powers org-scoped amount queries; partial index excludes NULL amounts.
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
    "idx_detections_org_amount "
    "ON detections(organization_id, amount_usd DESC) "
    "WHERE amount_usd IS NOT NULL",
    # Powers stalled_invoice + recovery_candidate rules.
    # Partial index keeps it small by excluding already-paid invoices.
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
    "idx_invoices_status_created "
    "ON invoices(status, created_at) "
    "WHERE status != 'paid'",
    # Powers stale_lead rule — contacts with no recent activity.
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
    "idx_contacts_updated "
    "ON contacts(updated_at DESC)",
]

_DOWNGRADE_SQLS = [
    "DROP INDEX CONCURRENTLY IF EXISTS idx_contacts_updated",
    "DROP INDEX CONCURRENTLY IF EXISTS idx_invoices_status_created",
    "DROP INDEX CONCURRENTLY IF EXISTS idx_detections_org_amount",
    "DROP INDEX CONCURRENTLY IF EXISTS idx_detections_run_amount",
    "DROP INDEX CONCURRENTLY IF EXISTS idx_insights_org_generated",
    "DROP INDEX CONCURRENTLY IF EXISTS idx_detection_runs_org_started",
]


def _run_concurrently(sqls: list[str]) -> None:
    """Execute each SQL on a separate AUTOCOMMIT connection (required by CONCURRENTLY)."""
    # op.get_bind() returns the migration connection which is already in a
    # transaction. CONCURRENTLY needs a connection outside any transaction,
    # so we open a second connection from the same engine in AUTOCOMMIT mode.
    engine = op.get_bind().engine
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for sql in sqls:
            conn.execute(sa.text(sql))


def upgrade() -> None:
    _run_concurrently(_UPGRADE_SQLS)


def downgrade() -> None:
    _run_concurrently(_DOWNGRADE_SQLS)
