from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CloudProvider, ResourceStatus


class IngestionRequest(BaseModel):
    providers: list[CloudProvider] = Field(default_factory=lambda: list(CloudProvider))
    start_date: date | None = None
    end_date: date | None = None
    include_resources: bool = True
    use_sample_data: bool = False


class ProviderSyncResultResponse(BaseModel):
    provider: CloudProvider
    status: str
    account_id: UUID | None = None
    cost_records_ingested: int
    resources_ingested: int
    errors: list[str]


class IngestionSummaryResponse(BaseModel):
    start_date: date
    end_date: date
    total_cost_records: int
    total_resources: int
    results: list[ProviderSyncResultResponse]


class CloudAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: CloudProvider
    external_account_id: str
    display_name: str


class CostRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    usage_date: date
    service_name: str
    region: str | None
    amount: Decimal
    currency: str
    granularity: str
    dimensions: dict


class CloudResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    external_resource_id: str
    resource_type: str
    region: str | None
    status: ResourceStatus
    estimated_monthly_cost: Decimal | None
    tags: dict
    metadata_json: dict
    idle_reason: str | None