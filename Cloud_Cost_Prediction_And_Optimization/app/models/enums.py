from enum import StrEnum


class CloudProvider(StrEnum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"


class ResourceStatus(StrEnum):
    ACTIVE = "active"
    IDLE = "idle"
    STOPPED = "stopped"
    TERMINATED = "terminated"
    UNKNOWN = "unknown"


class RemediationStatus(StrEnum):
    REQUESTED = "requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
