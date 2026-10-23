"""Persist jobs, dispatch requests, snapshots, and original extracted records."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0001_local_jobs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("configuration", JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("claim_token", sa.Uuid()),
        sa.Column("last_error", sa.Text()),
        sa.Column("attempt_log", JSONB(), nullable=False),
        sa.CheckConstraint("attempts BETWEEN 0 AND 3", name="ck_job_attempts"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_job_status",
        ),
    )
    op.create_table(
        "job_outbox",
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column("next_dispatch_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_job_outbox_next_dispatch_at", "job_outbox", ["next_dispatch_at"])
    op.create_table(
        "snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        sa.UniqueConstraint("job_id", "attempt", name="uq_snapshot_attempt"),
    )
    op.create_index("ix_snapshots_job_id", "snapshots", ["job_id"])
    op.create_table(
        "product_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("jobs.id"), nullable=False, unique=True),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("snapshots.id"), nullable=False),
        sa.Column("fields", JSONB(), nullable=False),
        sa.Column("extraction_method", sa.String(32), nullable=False),
        sa.Column("validation_status", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    # Explicitly user-run only: downgrading this initial revision removes its data.
    op.drop_table("product_records")
    op.drop_table("snapshots")
    op.drop_table("job_outbox")
    op.drop_table("jobs")
