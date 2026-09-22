import os
from datetime import datetime
from decimal import Decimal

from app.adapters.base import CloudAdapter, ProviderCostRecord, ProviderResource
from app.models.enums import CloudProvider, ResourceStatus


class AzureAdapter(CloudAdapter):
    provider = CloudProvider.AZURE

    def __init__(self, subscription_id: str | None = None):
        self.subscription_id = subscription_id or os.getenv("AZURE_SUBSCRIPTION_ID")
        self._cost_client = None
        self._compute_client = None

    def _clients(self):
        if not self.subscription_id:
            raise RuntimeError("Set AZURE_SUBSCRIPTION_ID to enable Azure ingestion")
        if self._cost_client and self._compute_client:
            return self._cost_client, self._compute_client
        try:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.compute import ComputeManagementClient
            from azure.mgmt.costmanagement import CostManagementClient
        except ImportError as exc:
            raise RuntimeError("Install azure-identity, azure-mgmt-costmanagement, and azure-mgmt-compute to enable Azure ingestion") from exc
        credential = DefaultAzureCredential()
        self._cost_client = CostManagementClient(credential)
        self._compute_client = ComputeManagementClient(credential, self.subscription_id)
        return self._cost_client, self._compute_client

    def collect_costs(self, start_date: str, end_date: str) -> list[ProviderCostRecord]:
        cost_client, _ = self._clients()
        scope = f"/subscriptions/{self.subscription_id}"
        parameters = {
            "type": "ActualCost",
            "timeframe": "Custom",
            "time_period": {"from_property": f"{start_date}T00:00:00Z", "to": f"{end_date}T00:00:00Z"},
            "dataset": {
                "granularity": "Daily",
                "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}},
                "grouping": [
                    {"type": "Dimension", "name": "ServiceName"},
                    {"type": "Dimension", "name": "ResourceLocation"},
                ],
            },
        }
        result = cost_client.query.usage(scope, parameters)
        columns = [column.name for column in getattr(result, "columns", [])]
        rows = getattr(result, "rows", []) or []

        records: list[ProviderCostRecord] = []
        for row in rows:
            row_map = dict(zip(columns, row, strict=False))
            raw_date = str(row_map.get("UsageDate") or row_map.get("Date"))
            usage_date = datetime.strptime(raw_date[:8], "%Y%m%d").date() if raw_date.isdigit() else datetime.fromisoformat(raw_date[:10]).date()
            records.append(
                ProviderCostRecord(
                    usage_date=usage_date,
                    service_name=str(row_map.get("ServiceName") or "Unknown"),
                    region=row_map.get("ResourceLocation"),
                    amount=Decimal(str(row_map.get("PreTaxCost") or row_map.get("Cost") or row_map.get("totalCost") or "0")),
                    currency=str(row_map.get("Currency") or "USD"),
                    dimensions={"provider": self.provider.value, "subscription_id": self.subscription_id},
                )
            )
        return records

    def find_idle_resources(self) -> list[ProviderResource]:
        _, compute_client = self._clients()
        resources: list[ProviderResource] = []
        for vm in compute_client.virtual_machines.list_all():
            instance_view = compute_client.virtual_machines.instance_view(self._resource_group_from_id(vm.id), vm.name)
            power_state = self._power_state(getattr(instance_view, "statuses", []) or [])
            if power_state and power_state.lower() in {"powerstate/deallocated", "powerstate/stopped"}:
                resources.append(
                    ProviderResource(
                        external_resource_id=vm.id,
                        resource_type="virtual_machine",
                        region=getattr(vm, "location", None),
                        status=ResourceStatus.IDLE,
                        tags=getattr(vm, "tags", None) or {},
                        metadata={"power_state": power_state, "vm_size": getattr(getattr(vm, "hardware_profile", None), "vm_size", None)},
                    )
                )
        for disk in compute_client.disks.list():
            if getattr(disk, "disk_state", None) == "Unattached":
                resources.append(
                    ProviderResource(
                        external_resource_id=disk.id,
                        resource_type="managed_disk",
                        region=getattr(disk, "location", None),
                        status=ResourceStatus.IDLE,
                        tags=getattr(disk, "tags", None) or {},
                        metadata={"reason": "Unattached Azure managed disk", "disk_size_gib": getattr(disk, "disk_size_gb", None)},
                    )
                )
        return resources

    @staticmethod
    def _resource_group_from_id(resource_id: str) -> str:
        parts = resource_id.split("/")
        return parts[parts.index("resourceGroups") + 1]

    @staticmethod
    def _power_state(statuses) -> str | None:
        for status in statuses:
            code = getattr(status, "code", "")
            if code.startswith("PowerState/"):
                return code
        return None

    def remediate(self, external_resource_id: str, action: str, region: str | None = None, resource_type: str | None = None) -> dict:
        if action not in {"stop", "delete"}:
            raise ValueError(f"Unsupported Azure remediation action: {action}")
        _, compute_client = self._clients()
        resource_group = self._resource_group_from_id(external_resource_id)
        vm_name = external_resource_id.rstrip("/").rsplit("/", 1)[-1]
        if resource_type == "managed_disk":
            if action != "delete":
                raise ValueError("Managed disks only support delete remediation")
            disk_name = external_resource_id.rstrip("/").rsplit("/", 1)[-1]
            result = compute_client.disks.begin_delete(resource_group, disk_name).result()
            return {"provider": self.provider.value, "action": action, "resource_group": resource_group, "result": str(result)}
        if action not in {"stop", "delete"}:
            raise ValueError(f"Unsupported Azure remediation action: {action}")
        if action == "stop":
            result = compute_client.virtual_machines.begin_deallocate(resource_group, vm_name).result()
        else:
            result = compute_client.virtual_machines.begin_delete(resource_group, vm_name).result()
        return {"provider": self.provider.value, "action": action, "resource_group": resource_group, "result": str(result)}