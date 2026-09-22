"""initial normalized finops schema

Revision ID: 20260904_0001
Revises:
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260904_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    provider = sa.Enum("AWS", "AZURE", "GCP", name="cloud_provider")
    resource_status = sa.Enum("ACTIVE", "IDLE", "STOPPED", "TERMINATED", "UNKNOWN", name="resource_status")
    remediation_status = sa.Enum("REQUESTED", "SUCCEEDED", "FAILED", "SKIPPED", name="remediation_status")
    provider.create(op.get_bind(), checkfirst=True)
    resource_status.create(op.get_bind(), checkfirst=True)
    remediation_status.create(op.get_bind(), checkfirst=True)
    op.create_table("cloud_accounts", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("provider", provider, nullable=False), sa.Column("external_account_id", sa.String(255), nullable=False), sa.Column("display_name", sa.String(255), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("provider", "external_account_id", name="uq_cloud_account_provider_external"))
    op.create_table("cloud_resources", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False), sa.Column("external_resource_id", sa.String(512), nullable=False), sa.Column("resource_type", sa.String(128), nullable=False), sa.Column("region", sa.String(128)), sa.Column("status", resource_status, nullable=False), sa.Column("estimated_monthly_cost", sa.Numeric(14, 4)), sa.Column("tags", postgresql.JSONB(), nullable=False), sa.Column("metadata", postgresql.JSONB(), nullable=False), sa.Column("idle_reason", sa.Text()), sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.UniqueConstraint("account_id", "external_resource_id", name="uq_resource_account_external"))
    op.create_index("ix_cloud_resources_account_id", "cloud_resources", ["account_id"])
    op.create_table("cost_records", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False), sa.Column("usage_date", sa.Date(), nullable=False), sa.Column("service_name", sa.String(255), nullable=False), sa.Column("region", sa.String(128)), sa.Column("amount", sa.Numeric(14, 4), nullable=False), sa.Column("currency", sa.String(3), nullable=False), sa.Column("granularity", sa.String(16), nullable=False), sa.Column("dimensions", postgresql.JSONB(), nullable=False), sa.Column("ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_cost_records_account_id", "cost_records", ["account_id"])
    op.create_index("ix_cost_records_usage_date", "cost_records", ["usage_date"])
    op.create_table("remediation_logs", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("resource_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cloud_resources.id", ondelete="CASCADE"), nullable=False), sa.Column("action", sa.String(64), nullable=False), sa.Column("status", remediation_status, nullable=False), sa.Column("requested_by", sa.String(255), nullable=False), sa.Column("provider_response", postgresql.JSONB(), nullable=False), sa.Column("error_message", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)))
    op.create_index("ix_remediation_logs_resource_id", "remediation_logs", ["resource_id"])


def downgrade() -> None:
    op.drop_table("remediation_logs")
    op.drop_table("cost_records")
    op.drop_table("cloud_resources")
    op.drop_table("cloud_accounts")
    sa.Enum(name="remediation_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="resource_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="cloud_provider").drop(op.get_bind(), checkfirst=True)
