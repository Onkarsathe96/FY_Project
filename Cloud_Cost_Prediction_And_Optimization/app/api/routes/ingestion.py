from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.adapters.aws import AWSAdapter
from app.models import CloudAccount, CloudResource, CostRecord
from app.models.enums import CloudProvider
from app.schemas.ingestion import (
    CloudAccountResponse,
    CloudResourceResponse,
    CostRecordResponse,
    IngestionRequest,
    IngestionSummaryResponse,
    ProviderSyncResultResponse,
)
from app.services.ingestion import default_date_window, sync_cloud_data

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.get("/connectivity/aws")
def check_aws_connectivity() -> dict[str, str | bool]:
    try:
        identity = AWSAdapter().get_account_identity()
    except (BotoCoreError, ClientError, RuntimeError, ValueError) as exc:
        return {"connected": False, "error": str(exc)}
    return {"connected": True, **identity}


@router.post("/sync", response_model=IngestionSummaryResponse, status_code=status.HTTP_202_ACCEPTED)
def sync_ingestion(request: IngestionRequest, db: Session = Depends(get_db)) -> IngestionSummaryResponse:
    start_date, end_date = _resolve_window(request.start_date, request.end_date)
    summary = sync_cloud_data(
        db=db,
        providers=request.providers,
        start_date=start_date,
        end_date=end_date,
        include_resources=request.include_resources,
        use_sample_data=request.use_sample_data,
    )
    return IngestionSummaryResponse(
        start_date=summary.start_date,
        end_date=summary.end_date,
        total_cost_records=summary.total_cost_records,
        total_resources=summary.total_resources,
        results=[ProviderSyncResultResponse(**result.__dict__) for result in summary.results],
    )


@router.get("/accounts", response_model=list[CloudAccountResponse])
def list_cloud_accounts(provider: CloudProvider | None = None, db: Session = Depends(get_db)) -> list[CloudAccount]:
    stmt = select(CloudAccount).order_by(CloudAccount.provider, CloudAccount.display_name)
    if provider:
        stmt = stmt.where(CloudAccount.provider == provider)
    return list(db.scalars(stmt).all())


@router.get("/costs", response_model=list[CostRecordResponse])
def list_cost_records(
    provider: CloudProvider | None = None,
    include_sample_data: bool = False,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[CostRecord]:
    stmt = select(CostRecord).join(CloudAccount).order_by(CostRecord.usage_date.desc(), CostRecord.service_name).limit(limit)
    if provider:
        stmt = stmt.where(CloudAccount.provider == provider)
    if not include_sample_data:
        stmt = stmt.where(~CloudAccount.external_account_id.endswith("-sample"))
    if start_date:
        stmt = stmt.where(CostRecord.usage_date >= start_date)
    if end_date:
        stmt = stmt.where(CostRecord.usage_date < end_date)
    return list(db.scalars(stmt).all())


@router.get("/resources", response_model=list[CloudResourceResponse])
def list_idle_resources(
    provider: CloudProvider | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[CloudResource]:
    stmt = select(CloudResource).join(CloudAccount).order_by(CloudResource.updated_at.desc()).limit(limit)
    if provider:
        stmt = stmt.where(CloudAccount.provider == provider)
    return list(db.scalars(stmt).all())


def _resolve_window(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    if start_date is None and end_date is None:
        return default_date_window()
    if start_date is None or end_date is None:
        raise HTTPException(status_code=400, detail="Provide both start_date and end_date, or neither for the default 7-day window")
    if start_date >= end_date:
        raise HTTPException(status_code=400, detail="start_date must be earlier than end_date")
    return start_date, end_date