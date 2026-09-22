output "aws_sandbox" { value = var.enable_aws ? module.aws_sandbox[0] : null }
output "azure_sandbox" { value = var.enable_azure ? module.azure_sandbox[0] : null }
output "gcp_sandbox" { value = var.enable_gcp ? module.gcp_sandbox[0] : null }
