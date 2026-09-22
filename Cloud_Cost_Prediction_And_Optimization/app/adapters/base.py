from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.models.enums import CloudProvider, ResourceStatus


@dataclass(frozen=True)
class ProviderCostRecord:
    usage_date: date
    service_name: str
    region: str | None
    amount: Decimal
    currency: str = "USD"
    granularity: str = "daily"
    dimensions: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResource:
    external_resource_id: str
    resource_type: str
    region: str | None
    status: ResourceStatus
    estimated_monthly_cost: Decimal | None = None
    tags: dict[str, str] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


class CloudAdapter(ABC):
    """Provider-neutral contract for discovery and explicitly approved remediation."""

    provider: CloudProvider

    @abstractmethod
    def collect_costs(self, start_date: str, end_date: str) -> list[ProviderCostRecord]:
        """Return provider cost entries in the normalized ingestion shape."""

    @abstractmethod
    def find_idle_resources(self) -> list[ProviderResource]:
        """Return candidate idle resources; this must never mutate cloud state."""

    @abstractmethod
    def remediate(
        self,
        external_resource_id: str,
        action: str,
        region: str | None = None,
        resource_type: str | None = None,
    ) -> dict:
        """Execute an explicitly approved provider action."""