variable "project_name" {
  type        = string
  default     = "Clould_Cost_Prediction_And_Optimization"
  description = "Project identifier used in tags and labels."
}

variable "environment" {
  type        = string
  default     = "sandbox"
  description = "Phase 2 is sandbox-only."

  validation {
    condition     = var.environment == "sandbox"
    error_message = "Phase 2 is restricted to sandbox."
  }
}

variable "enable_aws" {
  type    = bool
  default = false
}
variable "aws_region" {
  type    = string
  default = "ap-south-1"
}
variable "aws_vpc_cidr" {
  type    = string
  default = "10.30.0.0/16"
}
variable "aws_create_compute" {
  type        = bool
  default     = false
  description = "Creates a billable t3.micro test instance."
}

variable "enable_azure" {
  type    = bool
  default = false
}
variable "azure_subscription_id" {
  type     = string
  default  = null
  nullable = true
}
variable "azure_location" {
  type    = string
  default = "centralindia"
}
variable "azure_vnet_cidr" {
  type    = string
  default = "10.31.0.0/16"
}
variable "azure_create_compute" {
  type        = bool
  default     = false
  description = "Creates a billable Standard_B1s test VM."
}
variable "azure_admin_username" {
  type    = string
  default = "cloudcostadmin"
}
variable "azure_admin_ssh_public_key" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
}

variable "enable_gcp" {
  type    = bool
  default = false
}
variable "gcp_project_id" {
  type     = string
  default  = null
  nullable = true
}
variable "gcp_region" {
  type    = string
  default = "asia-south1"
}
variable "gcp_zone" {
  type    = string
  default = "asia-south1-a"
}
variable "gcp_subnet_cidr" {
  type    = string
  default = "10.32.0.0/20"
}
variable "gcp_create_compute" {
  type        = bool
  default     = false
  description = "Creates a billable e2-micro test instance."
}