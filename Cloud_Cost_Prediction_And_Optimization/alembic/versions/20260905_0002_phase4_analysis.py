"""add phase 4 forecasts and anomalies

Revision ID: 20260905_0002
Revises: 20260904_0001
Create Date: 2026-09-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260905_0002"
down_revision = "20260904_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cost_forecasts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_name", sa.String(255), nullable=False),
        sa.Column("region", sa.String(128)),
        sa.Column("forecast_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("predicted_amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("lower_bound", sa.Numeric(14, 4), nullable=False),
        sa.Column("upper_bound", sa.Numeric(14, 4), nullable=False),
        sa.Column("model_name", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cost_forecasts_account_id", "cost_forecasts", ["account_id"])
    op.create_index("ix_cost_forecasts_forecast_date", "cost_forecasts", ["forecast_date"])
    op.create_table(
        "cost_anomalies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_name", sa.String(255), nullable=False),
        sa.Column("region", sa.String(128)),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("actual_amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("expected_amount", sa.Numeric(14, 4), nullable=False),
        sa.Column("upper_bound", sa.Numeric(14, 4), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cost_anomalies_account_id", "cost_anomalies", ["account_id"])
    op.create_index("ix_cost_anomalies_usage_date", "cost_anomalies", ["usage_date"])


def downgrade() -> None:
    op.drop_table("cost_anomalies")
    op.drop_table("cost_forecasts")