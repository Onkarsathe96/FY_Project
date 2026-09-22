from app.adapters.base import CloudAdapter, ProviderCostRecord, ProviderResource
from app.models.enums import CloudProvider


class PlaceholderAdapter(CloudAdapter):
    """Fallback adapter used only when a provider implementation is unavailable."""

    provider: CloudProvider

    def collect_costs(self, start_date: str, end_date: str) -> list[ProviderCostRecord]:
        raise NotImplementedError(f"{self.provider.value} ingestion is not configured")

    def find_idle_resources(self) -> list[ProviderResource]:
        raise NotImplementedError(f"{self.provider.value} resource discovery is not configured")

    def remediate(self, external_resource_id: str, action: str, region: str | None = None) -> dict:
        raise NotImplementedError("Remediation is planned for Phase 5 and requires explicit approval")