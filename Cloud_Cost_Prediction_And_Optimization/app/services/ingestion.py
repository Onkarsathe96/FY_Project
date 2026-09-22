from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.adapters import get_adapter
from app.adapters.base import CloudAdapter, ProviderCostRecord, ProviderResource
from app.adapters.sample import SampleAdapter
from app.models import CloudAccount, CloudResource, CostAnomaly, CostForecast, CostRecord, RemediationLog
from app.models.enums import CloudProvider


@dataclass
class ProviderSyncResult:
    provider: CloudProvider
    status: str
    account_id: UUID | None = None
    cost_records_ingested: int = 0
    resources_ingested: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class IngestionSummary:
    start_date: date
    end_date: date
    results: list[ProviderSyncResult]

    @property
    def total_cost_records(self) -> int:
        return sum(result.cost_records_ingested for result in self.results)

    @property
    def total_resources(self) -> int:
        return sum(result.resources_ingested for result in self.results)


def default_date_window(days: int = 7) -> tuple[date, date]:
    end_date = date.today() + timedelta(days=1)
    start_date = end_date - timedelta(days=days)
    return start_date, end_date


def sync_cloud_data(
    db: Session,
    providers: list[CloudProvider],
    start_date: date,
    end_date: date,
    include_resources: bool = True,
    use_sample_data: bool = False,
) -> IngestionSummary:
    results: list[ProviderSyncResult] = []
    for provider in providers:
        result = _sync_provider(db, provider, start_date, end_date, include_resources, use_sample_data)
        results.append(result)
    db.commit()
    return IngestionSummary(start_date=start_date, end_date=end_date, results=results)


def _sync_provider(
    db: Session,
    provider: CloudProvider,
    start_date: date,
    end_date: date,
    include_resources: bool,
    use_sample_data: bool,
) -> ProviderSyncResult:
    adapter = _adapter_for(provider, use_sample_data)
    result = ProviderSyncResult(provider=provider, status="succeeded")

    try:
        account = _get_or_create_account(db, provider, use_sample_data, adapter)
        result.account_id = account.id
        costs = adapter.collect_costs(start_date.isoformat(), end_date.isoformat())
        result.cost_records_ingested = _replace_cost_records(db, account, costs, start_date, end_date)

        if include_resources:
            resources = adapter.find_idle_resources()
            result.resources_ingested = _upsert_resources(db, account, resources)
    except Exception as exc:  # Provider SDK failures should not stop other providers.
        db.rollback()
        result.status = "failed"
        result.errors.append(str(exc))
    return result


def _adapter_for(provider: CloudProvider, use_sample_data: bool) -> CloudAdapter:
    if use_sample_data:
        return SampleAdapter(provider)
    return get_adapter(provider)


def _get_or_create_account(db: Session, provider: CloudProvider, use_sample_data: bool, adapter: CloudAdapter) -> CloudAccount:
    identity = adapter.get_account_identity() if hasattr(adapter, "get_account_identity") and not use_sample_data else {}
    external_account_id = identity.get("account_id") or (f"{provider.value}-sample" if use_sample_data else f"{provider.value}-default")
    account = db.scalar(
        select(CloudAccount).where(
            CloudAccount.provider == provider,
            CloudAccount.external_account_id == external_account_id,
        )
    )
    if identity and not use_sample_data:
        legacy_account = db.scalar(
            select(CloudAccount).where(
                CloudAccount.provider == provider,
                CloudAccount.external_account_id == f"{provider.value}-default",
            )
        )
        if legacy_account and (account is None or legacy_account.id != account.id):
            db.execute(delete(CostRecord).where(CostRecord.account_id == legacy_account.id))
            db.execute(delete(CostForecast).where(CostForecast.account_id == legacy_account.id))
            db.execute(delete(CostAnomaly).where(CostAnomaly.account_id == legacy_account.id))
            legacy_resources = list(db.scalars(select(CloudResource).where(CloudResource.account_id == legacy_account.id)).all())
            for resource in legacy_resources:
                db.execute(delete(RemediationLog).where(RemediationLog.resource_id == resource.id))
            db.execute(delete(CloudResource).where(CloudResource.account_id == legacy_account.id))
            db.delete(legacy_account)
            db.flush()

    if account:
        return account

    account = CloudAccount(
        provider=provider,
        external_account_id=external_account_id,
        display_name=identity.get("account_id") and f"{provider.value.upper()} Account {identity['account_id']}" or f"{provider.value.upper()} {'Sample' if use_sample_data else 'Default'} Account",
    )
    db.add(account)
    db.flush()
    return account


def _replace_cost_records(
    db: Session,
    account: CloudAccount,
    costs: list[ProviderCostRecord],
    start_date: date,
    end_date: date,
) -> int:
    db.execute(
        delete(CostRecord).where(
            CostRecord.account_id == account.id,
            CostRecord.usage_date >= start_date,
            CostRecord.usage_date < end_date,
        )
    )
    for cost in costs:
        db.add(
            CostRecord(
                account_id=account.id,
                usage_date=cost.usage_date,
                service_name=cost.service_name,
                region=cost.region,
                amount=Decimal(cost.amount),
                currency=cost.currency,
                granularity=cost.granularity,
                dimensions=cost.dimensions,
            )
        )
    db.flush()
    return len(costs)


def _upsert_resources(db: Session, account: CloudAccount, resources: list[ProviderResource]) -> int:
    for resource in resources:
        existing = db.scalar(
            select(CloudResource).where(
                CloudResource.account_id == account.id,
                CloudResource.external_resource_id == resource.external_resource_id,
            )
        )
        if existing:
            existing.resource_type = resource.resource_type
            existing.region = resource.region
            existing.status = resource.status
            existing.estimated_monthly_cost = resource.estimated_monthly_cost
            existing.tags = resource.tags
            existing.metadata_json = resource.metadata
            existing.idle_reason = resource.metadata.get("reason") if isinstance(resource.metadata, dict) else None
        else:
            db.add(
                CloudResource(
                    account_id=account.id,
                    external_resource_id=resource.external_resource_id,
                    resource_type=resource.resource_type,
                    region=resource.region,
                    status=resource.status,
                    estimated_monthly_cost=resource.estimated_monthly_cost,
                    tags=resource.tags,
                    metadata_json=resource.metadata,
                    idle_reason=resource.metadata.get("reason") if isinstance(resource.metadata, dict) else None,
                )
            )
    db.flush()
    return len(resources)