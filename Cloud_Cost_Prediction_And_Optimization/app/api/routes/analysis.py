from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import CloudAccount, CostAnomaly, CostForecast
from app.models.enums import CloudProvider
from app.schemas.analysis import AnalysisRequest, AnalysisSummaryResponse, CostAnomalyResponse, CostForecastResponse
from app.services.analytics import run_cost_analysis

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/run", response_model=AnalysisSummaryResponse, status_code=status.HTTP_201_CREATED)
def run_analysis(request: AnalysisRequest, db: Session = Depends(get_db)) -> AnalysisSummaryResponse:
    summary = run_cost_analysis(
        db,
        request.providers,
        request.forecast_days,
        request.prefer_prophet,
        request.include_sample_data,
    )
    return AnalysisSummaryResponse(**summary.__dict__)


@router.get("/forecasts", response_model=list[CostForecastResponse])
def list_forecasts(
    provider: CloudProvider | None = None,
    include_sample_data: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[CostForecast]:
    stmt = select(CostForecast).join(CloudAccount).order_by(CostForecast.forecast_date, CostForecast.service_name).limit(limit)
    if provider:
        stmt = stmt.where(CloudAccount.provider == provider)
    if not include_sample_data:
        stmt = stmt.where(~CloudAccount.external_account_id.endswith("-sample"))
    if start_date:
        stmt = stmt.where(CostForecast.forecast_date >= start_date)
    if end_date:
        stmt = stmt.where(CostForecast.forecast_date < end_date)
    return list(db.scalars(stmt).all())


@router.get("/anomalies", response_model=list[CostAnomalyResponse])
def list_anomalies(
    provider: CloudProvider | None = None,
    include_sample_data: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[CostAnomaly]:
    stmt = select(CostAnomaly).join(CloudAccount).order_by(CostAnomaly.usage_date.desc()).limit(limit)
    if provider:
        stmt = stmt.where(CloudAccount.provider == provider)
    if not include_sample_data:
        stmt = stmt.where(~CloudAccount.external_account_id.endswith("-sample"))
    if start_date:
        stmt = stmt.where(CostAnomaly.usage_date >= start_date)
    if end_date:
        stmt = stmt.where(CostAnomaly.usage_date < end_date)
    return list(db.scalars(stmt).all())