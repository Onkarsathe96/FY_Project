import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.adapters.base import CloudAdapter, ProviderCostRecord, ProviderResource
from app.core.config import get_settings
from app.models.enums import CloudProvider, ResourceStatus


class AWSAdapter(CloudAdapter):
    provider = CloudProvider.AWS

    def __init__(self, region_name: str | None = None, profile_name: str | None = None):
        settings = get_settings()
        self.region_name = region_name or os.getenv("AWS_REGION") or settings.aws_region
        self.profile_name = profile_name or os.getenv("AWS_PROFILE") or settings.aws_profile

    def _session(self):
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("Install boto3 to enable AWS ingestion") from exc
        return boto3.Session(profile_name=self.profile_name, region_name=self.region_name)

    def get_account_identity(self) -> dict[str, str]:
        """Validate credentials and return non-secret AWS caller identity data."""
        identity = self._session().client("sts").get_caller_identity()
        return {
            "account_id": identity["Account"],
            "arn": identity["Arn"],
            "user_id": identity["UserId"],
            "region": self.region_name or "default",
            "profile": self.profile_name or "environment/default",
        }

    def collect_costs(self, start_date: str, end_date: str) -> list[ProviderCostRecord]:
        client = self._session().client("ce")
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
            GroupBy=[
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "REGION"},
            ],
        )

        records: list[ProviderCostRecord] = []
        for day in response.get("ResultsByTime", []):
            usage_date = datetime.strptime(day["TimePeriod"]["Start"], "%Y-%m-%d").date()
            for group in day.get("Groups", []):
                service_name, region = (group.get("Keys") or ["Unknown", None])[:2]
                amount_block = group["Metrics"]["UnblendedCost"]
                records.append(
                    ProviderCostRecord(
                        usage_date=usage_date,
                        service_name=service_name or "Unknown",
                        region=region or None,
                        amount=Decimal(str(amount_block.get("Amount", "0"))),
                        currency=amount_block.get("Unit", "USD"),
                        dimensions={"provider": self.provider.value},
                    )
                )
        return records

    def find_idle_resources(self) -> list[ProviderResource]:
        session = self._session()
        resources: list[ProviderResource] = self._empty_s3_buckets(session)
        try:
            regions = self._enabled_regions(session)
        except Exception:
            regions = [self.region_name or "us-east-1"]
        if not regions:
            regions = [self.region_name or "us-east-1"]
        for region in regions:
            try:
                ec2 = session.client("ec2", region_name=region)
                resources.extend(self._stopped_instances(ec2, region))
                resources.extend(self._unattached_volumes(ec2, region))
                resources.extend(self._low_cpu_instances(session, ec2, region))
            except Exception:
                continue
        return resources

    @staticmethod
    def _enabled_regions(session) -> list[str]:
        ec2 = session.client("ec2", region_name="us-east-1")
        return [region["RegionName"] for region in ec2.describe_regions(AllRegions=False).get("Regions", [])]

    @staticmethod
    def _stopped_instances(ec2, region: str) -> list[ProviderResource]:
        resources: list[ProviderResource] = []
        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate(Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}]):
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    tags = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}
                    resources.append(
                        ProviderResource(
                            external_resource_id=instance["InstanceId"],
                            resource_type="ec2_instance",
                            region=region,
                            status=ResourceStatus.IDLE,
                            tags=tags,
                            metadata={"state": instance.get("State", {}).get("Name"), "instance_type": instance.get("InstanceType"), "reason": "Stopped EC2 instance"},
                        )
                    )
        return resources

    @staticmethod
    def _unattached_volumes(ec2, region: str) -> list[ProviderResource]:
        resources: list[ProviderResource] = []
        paginator = ec2.get_paginator("describe_volumes")
        for page in paginator.paginate(Filters=[{"Name": "status", "Values": ["available"]}]):
            for volume in page.get("Volumes", []):
                tags = {tag["Key"]: tag["Value"] for tag in volume.get("Tags", [])}
                resources.append(
                    ProviderResource(
                        external_resource_id=volume["VolumeId"],
                        resource_type="ebs_volume",
                        region=region,
                        status=ResourceStatus.IDLE,
                        tags=tags,
                        metadata={"size_gib": volume.get("Size"), "volume_type": volume.get("VolumeType"), "reason": "Unattached EBS volume"},
                    )
                )
        return resources

    @staticmethod
    def _low_cpu_instances(session, ec2, region: str) -> list[ProviderResource]:
        try:
            cloudwatch = session.client("cloudwatch", region_name=region)
        except Exception:
            cloudwatch = None
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=7)
        resources: list[ProviderResource] = []
        paginator = ec2.get_paginator("describe_instances")
        for page in paginator.paginate(Filters=[{"Name": "instance-state-name", "Values": ["running"]}]):
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):
                    instance_id = instance["InstanceId"]
                    try:
                        metrics = cloudwatch.get_metric_statistics(
                            Namespace="AWS/EC2",
                            MetricName="CPUUtilization",
                            Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
                            StartTime=start_time,
                            EndTime=end_time,
                            Period=86400,
                            Statistics=["Average"],
                        ).get("Datapoints", []) if cloudwatch else []
                    except Exception:
                        metrics = []
                    averages = [point["Average"] for point in metrics if "Average" in point]
                    average_cpu = round(sum(averages) / len(averages), 2) if averages else None
                    reason = (
                        "Low EC2 CPU utilization over the last 7 days"
                        if average_cpu is not None and average_cpu < 5
                        else "Running EC2 instance requires optimization review"
                    )
                    tags = {tag["Key"]: tag["Value"] for tag in instance.get("Tags", [])}
                    resources.append(
                        ProviderResource(
                            external_resource_id=instance_id,
                            resource_type="ec2_instance",
                            region=region,
                            status=ResourceStatus.ACTIVE,
                            tags=tags,
                            metadata={
                                "reason": reason,
                                "average_cpu_percent": average_cpu,
                                "instance_type": instance.get("InstanceType"),
                            },
                        )
                    )
        return resources

    @staticmethod
    def _empty_s3_buckets(session) -> list[ProviderResource]:
        resources: list[ProviderResource] = []
        s3 = session.client("s3")
        for bucket in s3.list_buckets().get("Buckets", []):
            bucket_name = bucket["Name"]
            try:
                objects = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
            except Exception:
                continue
            if objects.get("KeyCount", 0) != 0:
                continue
            try:
                location = s3.get_bucket_location(Bucket=bucket_name).get("LocationConstraint")
            except Exception:
                location = None
            resources.append(
                ProviderResource(
                    external_resource_id=bucket_name,
                    resource_type="s3_bucket",
                    region=location or "us-east-1",
                    status=ResourceStatus.IDLE,
                    metadata={"reason": "Empty S3 bucket", "created": bucket.get("CreationDate").isoformat() if bucket.get("CreationDate") else None},
                )
            )
        return resources

    def remediate(
        self,
        external_resource_id: str,
        action: str,
        region: str | None = None,
        resource_type: str | None = None,
    ) -> dict:
        if action not in {"stop", "delete"}:
            raise ValueError(f"Unsupported AWS remediation action: {action}")
        session = self._session()
        if resource_type == "s3_bucket":
            if action != "delete":
                raise ValueError("S3 buckets only support delete remediation")
            response = session.client("s3", region_name=region or "us-east-1").delete_bucket(Bucket=external_resource_id)
            return {"provider": self.provider.value, "action": action, "response": response}
        ec2 = session.client("ec2", region_name=region or self.region_name or "us-east-1")
        if external_resource_id.startswith("i-"):
            if action == "stop":
                response = ec2.stop_instances(InstanceIds=[external_resource_id])
            else:
                response = ec2.terminate_instances(InstanceIds=[external_resource_id])
        elif external_resource_id.startswith("vol-") and action == "delete":
            response = ec2.delete_volume(VolumeId=external_resource_id)
        else:
            raise ValueError(f"Action {action} is not supported for AWS resource {external_resource_id}")
        return {"provider": self.provider.value, "action": action, "response": response}