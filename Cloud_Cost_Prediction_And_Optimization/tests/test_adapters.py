import pytest

from app.adapters import get_adapter
from app.models.enums import CloudProvider


@pytest.mark.parametrize("provider", list(CloudProvider))
def test_registry_returns_matching_adapter(provider):
    assert get_adapter(provider).provider is provider


def test_phase_one_adapter_blocks_mutating_work():
    response = get_adapter(CloudProvider.AWS)
    assert response.provider is CloudProvider.AWS


def test_sample_adapter_simulates_approved_actions():
    from app.adapters.sample import SampleAdapter

    result = SampleAdapter(CloudProvider.AWS).remediate("sample-idle", "stop")

    assert result["simulated"] is True
    assert result["action"] == "stop"


def test_sample_adapter_rejects_unknown_actions():
    from app.adapters.sample import SampleAdapter

    with pytest.raises(ValueError, match="Unsupported"):
        SampleAdapter(CloudProvider.AWS).remediate("sample-idle", "resize")


def test_aws_finds_empty_s3_buckets(monkeypatch):
    from app.adapters.aws import AWSAdapter

    class FakeS3:
        def list_buckets(self):
            return {"Buckets": [{"Name": "empty-bucket"}]}

        def list_objects_v2(self, **kwargs):
            return {"KeyCount": 0}

        def get_bucket_location(self, **kwargs):
            return {"LocationConstraint": None}

    class FakeSession:
        def client(self, service, **kwargs):
            if service == "s3":
                return FakeS3()
            raise AssertionError(f"Unexpected client: {service}")

    adapter = AWSAdapter()
    monkeypatch.setattr(adapter, "_session", lambda: FakeSession())
    monkeypatch.setattr(adapter, "_enabled_regions", lambda session: [])

    resources = adapter.find_idle_resources()

    assert len(resources) == 1
    assert resources[0].resource_type == "s3_bucket"
    assert resources[0].external_resource_id == "empty-bucket"


def test_aws_deletes_s3_bucket(monkeypatch):
    from app.adapters.aws import AWSAdapter

    calls = []

    class FakeS3:
        def delete_bucket(self, **kwargs):
            calls.append(kwargs)
            return {"ResponseMetadata": {"HTTPStatusCode": 204}}

    class FakeSession:
        def client(self, service, **kwargs):
            assert service == "s3"
            return FakeS3()

    adapter = AWSAdapter()
    monkeypatch.setattr(adapter, "_session", lambda: FakeSession())

    result = adapter.remediate("empty-bucket", "delete", "us-east-1", "s3_bucket")

    assert result["action"] == "delete"
    assert calls == [{"Bucket": "empty-bucket"}]


def test_aws_keeps_s3_candidates_when_ec2_region_scan_fails(monkeypatch):
    from app.adapters.aws import AWSAdapter

    class FakeS3:
        def list_buckets(self):
            return {"Buckets": [{"Name": "empty-bucket"}]}

        def list_objects_v2(self, **kwargs):
            return {"KeyCount": 0}

        def get_bucket_location(self, **kwargs):
            return {"LocationConstraint": None}

    class FakeSession:
        def client(self, service, **kwargs):
            if service == "s3":
                return FakeS3()
            raise RuntimeError("ec2 permission denied")

    adapter = AWSAdapter()
    monkeypatch.setattr(adapter, "_session", lambda: FakeSession())

    resources = adapter.find_idle_resources()

    assert [resource.external_resource_id for resource in resources] == ["empty-bucket"]


def test_aws_finds_unattached_ebs_and_stopped_ec2(monkeypatch):
    from app.adapters.aws import AWSAdapter

    class FakeEC2:
        def get_paginator(self, operation):
            class Paginator:
                def paginate(self, Filters):
                    if Filters[0]["Name"] == "status":
                        return [{"Volumes": [{"VolumeId": "vol-123", "Size": 20, "VolumeType": "gp3", "Tags": []}]}]
                    state = Filters[0]["Values"][0]
                    return [{"Reservations": [{"Instances": [{"InstanceId": "i-123", "InstanceType": "t3.micro", "State": {"Name": state}, "Tags": []}]}]}]
            return Paginator()

    class FakeCloudWatch:
        def get_metric_statistics(self, **kwargs):
            return {"Datapoints": []}

    class FakeS3:
        def list_buckets(self):
            return {"Buckets": []}

    class FakeSession:
        def client(self, service, **kwargs):
            return {"ec2": FakeEC2, "cloudwatch": FakeCloudWatch, "s3": FakeS3}[service]()

    adapter = AWSAdapter(region_name="eu-west-1")
    monkeypatch.setattr(adapter, "_session", lambda: FakeSession())
    monkeypatch.setattr(adapter, "_enabled_regions", lambda session: [])

    resources = adapter.find_idle_resources()

    assert {(resource.resource_type, resource.external_resource_id) for resource in resources} == {
        ("ebs_volume", "vol-123"),
        ("ec2_instance", "i-123"),
    }


def test_aws_remediates_ebs_and_ec2(monkeypatch):
    from app.adapters.aws import AWSAdapter

    calls = []

    class FakeEC2:
        def delete_volume(self, **kwargs):
            calls.append(("delete_volume", kwargs))
            return {}

        def stop_instances(self, **kwargs):
            calls.append(("stop_instances", kwargs))
            return {}

        def terminate_instances(self, **kwargs):
            calls.append(("terminate_instances", kwargs))
            return {}

    class FakeSession:
        def client(self, service, **kwargs):
            assert service == "ec2"
            return FakeEC2()

    adapter = AWSAdapter()
    monkeypatch.setattr(adapter, "_session", lambda: FakeSession())

    adapter.remediate("vol-123", "delete", "us-east-1", "ebs_volume")
    adapter.remediate("i-123", "stop", "us-east-1", "ec2_instance")
    adapter.remediate("i-123", "delete", "us-east-1", "ec2_instance")

    assert calls == [
        ("delete_volume", {"VolumeId": "vol-123"}),
        ("stop_instances", {"InstanceIds": ["i-123"]}),
        ("terminate_instances", {"InstanceIds": ["i-123"]}),
    ]


def test_aws_finds_running_ec2_without_cloudwatch_permission(monkeypatch):
    from app.adapters.aws import AWSAdapter

    class FakeEC2:
        def get_paginator(self, operation):
            class Paginator:
                def paginate(self, Filters):
                    if Filters[0]["Values"] == ["stopped"]:
                        return [{"Reservations": []}]
                    if Filters[0]["Name"] == "status":
                        return [{"Volumes": []}]
                    return [{"Reservations": [{"Instances": [{"InstanceId": "i-running", "InstanceType": "t3.micro", "State": {"Name": "running"}, "Tags": []}]}]}]
            return Paginator()

    class FakeS3:
        def list_buckets(self):
            return {"Buckets": []}

    class FakeSession:
        def client(self, service, **kwargs):
            if service == "cloudwatch":
                raise RuntimeError("cloudwatch permission denied")
            return FakeS3() if service == "s3" else FakeEC2()

    adapter = AWSAdapter(region_name="ap-south-2")
    monkeypatch.setattr(adapter, "_session", lambda: FakeSession())
    monkeypatch.setattr(adapter, "_enabled_regions", lambda session: ["ap-south-2"])

    resources = adapter.find_idle_resources()

    assert len(resources) == 1
    assert resources[0].external_resource_id == "i-running"
    assert resources[0].status.value == "active"
