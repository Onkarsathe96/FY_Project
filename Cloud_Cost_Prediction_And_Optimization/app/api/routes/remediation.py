from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import CloudAccount, CloudResource, RemediationLog
from app.models.enums import CloudProvider, ResourceStatus
from app.schemas.ingestion import CloudResourceResponse
from app.schemas.remediation import RemediationRequest, RemediationResponse
from app.services.remediation import RemediationError, execute_remediation

router = APIRouter(prefix="/remediation", tags=["remediation"])


@router.get("/resources", response_model=list[CloudResourceResponse])
def list_remediation_candidates(
    provider: CloudProvider | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[CloudResource]:
    stmt = (
        select(CloudResource)
        .join(CloudAccount)
        .where(CloudResource.status.in_((ResourceStatus.ACTIVE, ResourceStatus.IDLE, ResourceStatus.STOPPED)))
        .order_by(CloudResource.estimated_monthly_cost.desc().nullslast())
        .limit(limit)
    )
    if provider:
        stmt = stmt.where(CloudAccount.provider == provider)
    resources = list(db.scalars(stmt).all())
    unique_resources: dict[tuple[CloudProvider, str], CloudResource] = {}
    for resource in resources:
        key = (resource.account.provider, resource.external_resource_id)
        current = unique_resources.get(key)
        if current is None or _account_priority(resource.account.external_account_id) > _account_priority(current.account.external_account_id):
            unique_resources[key] = resource
    return list(unique_resources.values())


def _account_priority(external_account_id: str) -> int:
    if external_account_id.endswith("-sample"):
        return 0
    if external_account_id.endswith("-default"):
        return 1
    return 2


@router.post(
    "/resources/{resource_id}",
    response_model=RemediationResponse,
    status_code=status.HTTP_201_CREATED,
)
def remediate_resource(
    resource_id: UUID,
    request: RemediationRequest,
    db: Session = Depends(get_db),
) -> RemediationLog:
    try:
        return execute_remediation(
            db,
            resource_id,
            request.action,
            request.requested_by,
            request.approved,
        )
    except RemediationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/logs", response_model=list[RemediationResponse])
def list_remediation_logs(
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[RemediationLog]:
    stmt = select(RemediationLog).order_by(RemediationLog.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())
