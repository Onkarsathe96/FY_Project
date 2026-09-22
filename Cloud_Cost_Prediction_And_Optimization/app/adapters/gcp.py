import os
from decimal import Decimal

from app.adapters.base import CloudAdapter, ProviderCostRecord, ProviderResource
from app.models.enums import CloudProvider, ResourceStatus


class GCPAdapter(CloudAdapter):
    provider = CloudProvider.GCP

    def __init__(self, project_id: str | None = None, billing_export_table: str | None = None):
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.billing_export_table = billing_export_table or os.getenv("GCP_BILLING_EXPORT_TABLE")
        self._bigquery = None
        self._compute_v1 = None
        self._bq_client = None

    def _clients(self):
        if not self.project_id:
            raise RuntimeError("Set GCP_PROJECT_ID to enable GCP ingestion")
        if self._bigquery and self._compute_v1 and self._bq_client:
            return self._bigquery, self._compute_v1, self._bq_client
        try:
            from google.cloud import bigquery, compute_v1
        except ImportError as exc:
            raise RuntimeError("Install google-cloud-bigquery and google-cloud-compute to enable GCP ingestion") from exc
        self._bigquery = bigquery
        self._compute_v1 = compute_v1
        self._bq_client = bigquery.Client(project=self.project_id)
        return self._bigquery, self._compute_v1, self._bq_client

    def collect_costs(self, start_date: str, end_date: str) -> list[ProviderCostRecord]:
        bigquery, _, bq_client = self._clients()
        if not self.billing_export_table:
            raise RuntimeError("Set GCP_BILLING_EXPORT_TABLE to read GCP Billing Export rows from BigQuery")

        query = f"""
            SELECT
              DATE(usage_start_time) AS usage_date,
              service.description AS service_name,
              location.region AS region,
              SUM(cost) AS amount,
              currency
            FROM `{self.billing_export_table}`
            WHERE DATE(usage_start_time) >= @start_date
              AND DATE(usage_start_time) < @end_date
            GROUP BY usage_date, service_name, region, currency
            ORDER BY usage_date
        """
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
                bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
            ]
        )
        rows = bq_client.query(query, job_config=job_config).result()
        return [
            ProviderCostRecord(
                usage_date=row.usage_date,
                service_name=row.service_name or "Unknown",
                region=row.region,
                amount=Decimal(str(row.amount or "0")),
                currency=row.currency or "USD",
                dimensions={"provider": self.provider.value, "project_id": self.project_id},
            )
            for row in rows
        ]

    def find_idle_resources(self) -> list[ProviderResource]:
        _, compute_v1, _ = self._clients()
        resources: list[ProviderResource] = []
        request = compute_v1.AggregatedListInstancesRequest(project=self.project_id)
        client = compute_v1.InstancesClient()
        for zone_path, scoped_list in client.aggregated_list(request=request):
            zone = zone_path.rsplit("/", 1)[-1]
            for instance in getattr(scoped_list, "instances", []) or []:
                if instance.status in {"TERMINATED", "STOPPING", "SUSPENDED"}:
                    resources.append(
                        ProviderResource(
                            external_resource_id=str(getattr(instance, "self_link", None) or instance.id),
                            resource_type="compute_instance",
                            region=zone,
                            status=ResourceStatus.IDLE,
                            tags=dict(instance.labels or {}),
                            metadata={"name": instance.name, "status": instance.status, "machine_type": instance.machine_type},
                        )
                    )
        disk_client = compute_v1.DisksClient()
        disk_request = compute_v1.AggregatedListDisksRequest(project=self.project_id)
        for scope_path, scoped_list in disk_client.aggregated_list(request=disk_request):
            for disk in getattr(scoped_list, "disks", []) or []:
                if getattr(disk, "users", None):
                    continue
                disk_link = str(getattr(disk, "self_link", ""))
                resources.append(
                    ProviderResource(
                        external_resource_id=disk_link or str(disk.id),
                        resource_type="persistent_disk",
                        region=scope_path.rsplit("/", 1)[-1],
                        status=ResourceStatus.IDLE,
                        tags=dict(getattr(disk, "labels", {}) or {}),
                        metadata={"reason": "Unattached GCP persistent disk", "size_gib": getattr(disk, "size_gb", None)},
                    )
                )
        return resources

    def remediate(self, external_resource_id: str, action: str, region: str | None = None, resource_type: str | None = None) -> dict:
        if action not in {"stop", "delete"}:
            raise ValueError(f"Unsupported GCP remediation action: {action}")
        _, compute_v1, _ = self._clients()
        instance_name = external_resource_id.rsplit("/", 1)[-1]
        if resource_type == "persistent_disk":
            if action != "delete":
                raise ValueError("Persistent disks only support delete remediation")
            zone = external_resource_id.split("/zones/", 1)[-1].split("/", 1)[0] if "/zones/" in external_resource_id else None
            if not zone:
                raise ValueError("GCP persistent disk remediation requires a zonal disk resource path")
            operation = compute_v1.DisksClient().delete(project=self.project_id, zone=zone, disk=instance_name)
            return {"provider": self.provider.value, "action": action, "operation": str(operation)}
        zone = external_resource_id.split("/zones/", 1)[-1].split("/", 1)[0] if "/zones/" in external_resource_id else None
        if not zone:
            raise ValueError("GCP remediation requires a zonal instance resource path")
        client = compute_v1.InstancesClient()
        if action == "stop":
            operation = client.stop(project=self.project_id, zone=zone, instance=instance_name)
        else:
            operation = client.delete(project=self.project_id, zone=zone, instance=instance_name)
        return {"provider": self.provider.value, "action": action, "operation": str(operation)}