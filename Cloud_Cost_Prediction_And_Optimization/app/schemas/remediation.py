from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RemediationStatus


class RemediationRequest(BaseModel):
    action: str = Field(pattern="^(stop|delete)$")
    approved: bool = False
    requested_by: str = Field(default="dashboard", min_length=1, max_length=255)


class RemediationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    resource_id: UUID
    action: str
    status: RemediationStatus
    requested_by: str
    provider_response: dict
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
