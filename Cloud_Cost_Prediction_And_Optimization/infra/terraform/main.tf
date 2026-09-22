locals {
  resource_prefix = substr(replace(lower(var.project_name), "_", "-"), 0, 38)
  name_prefix     = "${local.resource_prefix}-${var.environment}-${random_id.suffix.hex}"
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
    Purpose     = "Clould_Cost_Prediction_And_Optimization-phase-2-sandbox"
  }
}

resource "random_id" "suffix" {
  byte_length = 3
}

module "aws_sandbox" {
  count          = var.enable_aws ? 1 : 0
  source         = "./modules/aws"
  name_prefix    = local.name_prefix
  vpc_cidr       = var.aws_vpc_cidr
  create_compute = var.aws_create_compute
  common_tags    = local.common_tags
}

module "azure_sandbox" {
  count                = var.enable_azure ? 1 : 0
  source               = "./modules/azure"
  name_prefix          = local.name_prefix
  location             = var.azure_location
  vnet_cidr            = var.azure_vnet_cidr
  create_compute       = var.azure_create_compute
  admin_username       = var.azure_admin_username
  admin_ssh_public_key = var.azure_admin_ssh_public_key
  common_tags          = local.common_tags
}

module "gcp_sandbox" {
  count          = var.enable_gcp ? 1 : 0
  source         = "./modules/gcp"
  name_prefix    = local.name_prefix
  region         = var.gcp_region
  zone           = var.gcp_zone
  subnet_cidr    = var.gcp_subnet_cidr
  create_compute = var.gcp_create_compute
  labels = {
    project     = local.resource_prefix
    environment = var.environment
    managed_by  = "terraform"
    purpose     = "clould-cost-prediction-and-optimization-phase-2-sandbox"
  }
}