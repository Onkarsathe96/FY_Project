from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import CloudProvider


class CloudAccount(Base):
    __tablename__ = "cloud_accounts"
    __table_args__ = (UniqueConstraint("provider", "external_account_id", name="uq_cloud_account_provider_external"),)

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    provider: Mapped[CloudProvider] = mapped_column(Enum(CloudProvider, name="cloud_provider"), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    resources = relationship("CloudResource", back_populates="account", cascade="all, delete-orphan")
    cost_records = relationship("CostRecord", back_populates="account", cascade="all, delete-orphan")
