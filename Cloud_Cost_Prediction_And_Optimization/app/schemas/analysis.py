from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CloudProvider


class AnalysisRequest(BaseModel):
    providers: list[CloudProvider] = Field(default_factory=lambda: list(CloudProvider))
    forecast_days: int = Field(default=7, ge=1, le=90)
    prefer_prophet: bool = True
    include_sample_data: bool = False


class AnalysisSummaryResponse(BaseModel):
    providers: list[CloudProvider]
    series_analysed: int
    series_skipped: int
    forecasts_created: int
    anomalies_detected: int
    model_names: list[str]


class CostForecastResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    service_name: str
    region: str | None
    forecast_date: date
    currency: str
    predicted_amount: Decimal
    lower_bound: Decimal
    upper_bound: Decimal
    model_name: str


class CostAnomalyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    service_name: str
    region: str | None
    usage_date: date
    currency: str
    actual_amount: Decimal
    expected_amount: Decimal
    upper_bound: Decimal
    severity: str
    explanation: str
    metadata_json: dict