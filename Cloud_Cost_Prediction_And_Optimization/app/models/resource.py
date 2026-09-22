from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ResourceStatus


class CloudResource(Base):
    __tablename__ = "cloud_resources"
    __table_args__ = (UniqueConstraint("account_id", "external_resource_id", name="uq_resource_account_external"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    external_resource_id: Mapped[str] = mapped_column(String(512), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    region: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[ResourceStatus] = mapped_column(Enum(ResourceStatus, name="resource_status"), default=ResourceStatus.UNKNOWN, nullable=False)
    estimated_monthly_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    tags: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    idle_reason: Mapped[str | None] = mapped_column(Text)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    account = relationship("CloudAccount", back_populates="resources")
