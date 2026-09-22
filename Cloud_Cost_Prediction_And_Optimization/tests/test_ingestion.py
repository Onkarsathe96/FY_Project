from datetime import date

from app.adapters.sample import SampleAdapter
from app.models.enums import CloudProvider, ResourceStatus
from app.services.ingestion import default_date_window


def test_sample_adapter_generates_daily_costs():
    adapter = SampleAdapter(CloudProvider.AWS)

    records = adapter.collect_costs("2026-09-01", "2026-09-03")

    assert len(records) == 4
    assert records[0].usage_date == date(2026, 9, 1)
    assert records[0].service_name == "Amazon EC2"
    assert records[0].dimensions["source"] == "sample"


def test_sample_adapter_returns_idle_resource_candidate():
    adapter = SampleAdapter(CloudProvider.GCP)

    resources = adapter.find_idle_resources()

    assert len(resources) == 1
    assert resources[0].status is ResourceStatus.IDLE
    assert resources[0].external_resource_id == "sample-gcp-idle-001"


def test_default_ingestion_window_is_valid():
    start_date, end_date = default_date_window()

    assert start_date < end_date
    assert (end_date - start_date).days == 7