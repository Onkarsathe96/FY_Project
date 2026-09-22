from app.adapters.aws import AWSAdapter
from app.adapters.azure import AzureAdapter
from app.adapters.base import CloudAdapter
from app.adapters.gcp import GCPAdapter
from app.models.enums import CloudProvider

_ADAPTERS: dict[CloudProvider, type[CloudAdapter]] = {
    CloudProvider.AWS: AWSAdapter,
    CloudProvider.AZURE: AzureAdapter,
    CloudProvider.GCP: GCPAdapter,
}


def get_adapter(provider: CloudProvider) -> CloudAdapter:
    return _ADAPTERS[provider]()
