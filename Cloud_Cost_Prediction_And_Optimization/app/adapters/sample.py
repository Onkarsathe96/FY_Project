from datetime import date, datetime, timedelta
from decimal import Decimal

from app.adapters.base import CloudAdapter, ProviderCostRecord, ProviderResource
from app.models.enums import CloudProvider, ResourceStatus


class SampleAdapter(CloudAdapter):
    """Deterministic local adapter for testing ingestion without cloud credentials."""

    def __init__(self, provider: CloudProvider):
        self.provider = provider

    def collect_costs(self, start_date: str, end_date: str) -> list[ProviderCostRecord]:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        services = {
            CloudProvider.AWS: ["Amazon EC2", "Amazon S3"],
            CloudProvider.AZURE: ["Virtual Machines", "Storage Accounts"],
            CloudProvider.GCP: ["Compute Engine", "Cloud Storage"],
        }[self.provider]
        regions = {
            CloudProvider.AWS: "us-east-1",
            CloudProvider.AZURE: "eastus",
            CloudProvider.GCP: "us-central1",
        }

        records: list[ProviderCostRecord] = []
        current = start
        day_index = 0
        while current < end:
            for service_index, service_name in enumerate(services, start=1):
                amount = Decimal("1.25") * Decimal(day_index + service_index)
                records.append(
                    ProviderCostRecord(
                        usage_date=current,
                        service_name=service_name,
                        region=regions[self.provider],
                        amount=amount,
                        dimensions={"provider": self.provider.value, "source": "sample"},
                    )
                )
            current += timedelta(days=1)
            day_index += 1
        return records

    def find_idle_resources(self) -> list[ProviderResource]:
        return [
            ProviderResource(
                external_resource_id=f"sample-{self.provider.value}-idle-001",
                resource_type="sample_idle_resource",
                region={CloudProvider.AWS: "us-east-1", CloudProvider.AZURE: "eastus", CloudProvider.GCP: "us-central1"}[self.provider],
                status=ResourceStatus.IDLE,
                estimated_monthly_cost=Decimal("12.50"),
                tags={"Environment": "sandbox", "Source": "sample"},
                metadata={"reason": "Phase 3 local verification data"},
            )
        ]

    def remediate(self, external_resource_id: str, action: str, region: str | None = None, resource_type: str | None = None) -> dict:
        if action not in {"stop", "delete"}:
            raise ValueError(f"Unsupported sample remediation action: {action}")
        return {
            "provider": self.provider.value,
            "action": action,
            "resource_id": external_resource_id,
            "simulated": True,
        }