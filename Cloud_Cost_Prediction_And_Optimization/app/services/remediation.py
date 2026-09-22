from datetime import datetime, timezone
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters import get_adapter
from app.adapters.sample import SampleAdapter
from app.models import CloudAccount, CloudResource, RemediationLog
from app.models.enums import RemediationStatus, ResourceStatus

ALLOWED_ACTIONS = frozenset({"stop", "delete"})


class RemediationError(ValueError):
    """Raised when a remediation request fails validation or provider execution."""


def execute_remediation(
    db: Session,
    resource_id: UUID,
    action: str,
    requested_by: str = "dashboard",
    approved: bool = False,
) -> RemediationLog:
    if not approved:
        raise RemediationError("Explicit approval is required before remediation")
    if action not in ALLOWED_ACTIONS:
        raise RemediationError(f"Unsupported remediation action: {action}")

    resource = db.scalar(
        select(CloudResource)
        .join(CloudAccount)
        .where(CloudResource.id == resource_id)
    )
    if resource is None:
        raise RemediationError("Cloud resource was not found")
    if resource.status == ResourceStatus.ACTIVE and resource.resource_type != "ec2_instance":
        raise RemediationError("Only EC2 instances can be remediated while active")
    if resource.status not in {ResourceStatus.ACTIVE, ResourceStatus.IDLE, ResourceStatus.STOPPED}:
        raise RemediationError("Only idle or stopped resources can be remediated")

    log = RemediationLog(
        resource_id=resource.id,
        action=action,
        status=RemediationStatus.REQUESTED,
        requested_by=requested_by,
        provider_response={},
    )
    db.add(log)
    db.flush()

    try:
        adapter = (
            SampleAdapter(resource.account.provider)
            if resource.account.external_account_id.endswith("-sample")
            else get_adapter(resource.account.provider)
        )
        response = adapter.remediate(resource.external_resource_id, action, resource.region, resource.resource_type)
    except (BotoCoreError, ClientError, RuntimeError, ValueError) as exc:
        log.status = RemediationStatus.FAILED
        log.error_message = _provider_error_message(exc)
        log.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise RemediationError(log.error_message) from exc

    log.status = RemediationStatus.SUCCEEDED
    log.provider_response = response
    log.completed_at = datetime.now(timezone.utc)
    resource.status = ResourceStatus.TERMINATED if action == "delete" else ResourceStatus.STOPPED
    db.commit()
    db.refresh(log)
    return log


def _provider_error_message(error: Exception) -> str:
    if isinstance(error, ClientError):
        error_code = error.response.get("Error", {}).get("Code", "AWS request failed")
        if error_code in {"UnauthorizedOperation", "AccessDenied", "AccessDeniedException"}:
            return "AWS denied this action. Grant the configured IAM identity the required permission for this resource and try again."
        return f"AWS request failed: {error_code}"
    return str(error)
