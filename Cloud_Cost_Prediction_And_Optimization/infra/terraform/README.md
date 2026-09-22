# Phase 2 Terraform sandbox

This configuration creates isolated, tagged sandbox networking in AWS, Azure, and GCP. All providers are disabled by default; enable exactly one cloud in `terraform.tfvars`. Compute is also disabled by default because it incurs cost.

## Prerequisites

- Terraform 1.6 or later.
- An authenticated cloud CLI/session for the provider being tested:
  - AWS: `aws configure` or workload credentials.
  - Azure: `az login`, plus a subscription ID in `terraform.tfvars` or environment.
  - GCP: `gcloud auth application-default login`, plus a project with Compute Engine API enabled.

## Safe workflow

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars
terraform init
terraform fmt -recursive -check
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

Review the plan before applying it. Terraform state contains resource identifiers and is ignored locally; move it to a protected remote backend before team or CI usage.

| Provider | Default resources | Optional compute |
| --- | --- | --- |
| AWS | VPC, private subnet, restrictive security group | one `t3.micro` EC2 instance |
| Azure | Resource group, VNet, subnet, NSG | one `Standard_B1s` Linux VM |
| GCP | Custom VPC, subnet, internal-only firewall | one `e2-micro` Compute Engine VM |

Default networking does not expose inbound internet access. Optional AWS/GCP instances have no public IP; the Azure VM has no public-IP resource.

## Teardown

When testing is complete, destroy only the reviewed sandbox state:

```powershell
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
```

Never run `destroy` against a workspace containing production resources.
