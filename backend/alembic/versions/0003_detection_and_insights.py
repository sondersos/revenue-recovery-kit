"""Create detection_runs, detections, and insights tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # detection_runs
    # ------------------------------------------------------------------
    op.create_table(
        "detection_runs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="running"),
        sa.Column("rule_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("detection_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('running', 'complete', 'failed')",
            name="ck_detection_runs_status",
        ),
    )

    # ------------------------------------------------------------------
    # detections  (FK → detection_runs)
    # ------------------------------------------------------------------
    op.create_table(
        "detections",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("detection_run_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("rule_name", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("amount_usd", sa.Numeric(12, 2), nullable=True),
        sa.Column("days_outstanding", sa.Integer(), nullable=True),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["detection_run_id"],
            ["detection_runs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH')",
            name="ck_detections_severity",
        ),
        sa.CheckConstraint(
            "subject_type IN ('contact', 'invoice')",
            name="ck_detections_subject_type",
        ),
    )
    op.create_index(
        "ix_detections_org_rule",
        "detections",
        ["organization_id", "rule_name"],
        unique=False,
    )
    op.create_index(
        "ix_detections_run",
        "detections",
        ["detection_run_id"],
        unique=False,
    )

    # ------------------------------------------------------------------
    # insights  (FK → detection_runs, unique per run)
    # ------------------------------------------------------------------
    op.create_table(
        "insights",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("detection_run_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("input_payload", JSONB(), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(8, 4), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["detection_run_id"],
            ["detection_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("detection_run_id", name="uq_insights_detection_run_id"),
    )

    # ------------------------------------------------------------------
    # Row-Level Security
    # NOTE: The application MUST execute:
    #   SET app.current_org_id = '<org-uuid>';
    # before any query against these tables, otherwise RLS will block
    # all rows (current_setting returns NULL and the cast fails).
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE detection_runs ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY detection_runs_org_isolation ON detection_runs
            USING (organization_id = current_setting('app.current_org_id', TRUE)::UUID);
        """
    )

    op.execute("ALTER TABLE detections ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY detections_org_isolation ON detections
            USING (organization_id = current_setting('app.current_org_id', TRUE)::UUID);
        """
    )

    op.execute("ALTER TABLE insights ENABLE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY insights_org_isolation ON insights
            USING (organization_id = current_setting('app.current_org_id', TRUE)::UUID);
        """
    )


def downgrade() -> None:
    op.drop_table("insights")
    op.drop_index("ix_detections_run", table_name="detections")
    op.drop_index("ix_detections_org_rule", table_name="detections")
    op.drop_table("detections")
    op.drop_table("detection_runs")
