# Phase 2 — Multi-Cloud Sandbox Infrastructure

## Purpose

Phase 2 provisions the optional, isolated cloud sandbox that later Cloud_Cost_Prediction_And_Optimization phases can use for ingestion, waste-detection, and remediation testing. It uses Terraform to define equivalent minimal environments for AWS, Azure, and Google Cloud Platform (GCP).

This phase is infrastructure-as-code only. It does **not** collect cloud costs, train a forecasting model, expose ingestion APIs, or stop/delete any resource.

## What was completed

- Created a reusable Terraform root module in `infra/terraform`.
- Added independent provider modules for AWS, Azure, and GCP.
- Added a provider-neutral tagging/labeling strategy for project, environment, ownership, and purpose.
- Added a generated, cloud-safe resource prefix. The full project identifier is retained in tags, while lower-case hyphenated names are used where cloud naming rules require them.
- Set all cloud providers to disabled by default.
- Set all optional compute instances to disabled by default, preventing accidental billable VM/EC2 creation.
- Added input variables, outputs, a sample `terraform.tfvars`, and Terraform-specific `.gitignore` rules.
- Initialized Terraform locally and validated the configuration successfully using `terraform fmt`, `terraform init -backend=false`, and `terraform validate`.

No cloud plan or apply command was run during Phase 2 completion. Therefore, no cloud resources were created.

## Files added in Phase 2

```text
infra/terraform/
├── versions.tf                     # Terraform and provider version constraints
├── providers.tf                    # AWS, AzureRM, and Google provider setup
├── main.tf                         # Shared naming/tags and provider module wiring
├── variables.tf                    # Safe defaults and provider-specific inputs
├── outputs.tf                      # Sandbox resource identifiers after apply
├── terraform.tfvars.example        # Copyable configuration template
├── README.md                       # Concise Terraform-specific guide
└── modules/
    ├── aws/
    │   ├── main.tf                 # VPC, subnet, security group, optional EC2
    │   ├── variables.tf
    │   └── outputs.tf
    ├── azure/
    │   ├── main.tf                 # Resource group, VNet, subnet, NSG, optional VM
    │   ├── variables.tf
    │   └── outputs.tf
    └── gcp/
        ├── main.tf                 # VPC, subnet, internal firewall, optional VM
        ├── variables.tf
        └── outputs.tf
```

The root `.gitignore` also excludes Terraform state, plan files, local variables, and downloaded plugins. The provider lock file `.terraform.lock.hcl` should be kept in source control when you use Git, so every environment resolves the same provider versions.

## Infrastructure design

```text
Terraform root module
        |
        +-- AWS module     -> VPC -> private subnet -> restrictive security group
        |                                      └-> optional private t3.micro EC2
        |
        +-- Azure module   -> resource group -> VNet -> subnet -> NSG
        |                                              └-> optional private Standard_B1s VM
        |
        +-- GCP module     -> custom VPC -> subnet -> internal-only firewall
                                                       └-> optional private e2-micro VM
```

### AWS resources

By default, enabling AWS creates:

- One VPC
- One subnet configured not to assign public IP addresses
- One security group with no inbound rules and outbound HTTPS only

Setting `aws_create_compute = true` additionally creates one monitored `t3.micro` EC2 instance with no public IP address.

### Azure resources

By default, enabling Azure creates:

- One resource group
- One virtual network and subnet
- One network security group with no inbound rules

Setting `azure_create_compute = true` additionally creates one `Standard_B1s` Ubuntu VM and private network interface. An SSH public key is required; no public-IP resource is created.

### GCP resources

By default, enabling GCP creates:

- One custom-mode VPC
- One subnet
- One firewall rule allowing only traffic from the sandbox subnet

Setting `gcp_create_compute = true` additionally creates one `e2-micro` Debian VM with a private network interface and no external IP.

## Safety controls

| Control | How it protects the environment |
| --- | --- |
| Provider opt-in | `enable_aws`, `enable_azure`, and `enable_gcp` default to `false`. |
| Compute opt-in | Each `*_create_compute` variable defaults to `false`. |
| Sandbox-only guard | `environment` accepts only `sandbox`. |
| No public instance IPs | Optional AWS and GCP VMs have no public IP; Azure creates no public-IP resource. |
| No inbound internet rules | Default security group/NSG has no inbound rule; GCP firewall is subnet-only. |
| Explicit approval | Terraform changes occur only after a human reviews and runs `terraform apply`. |
| Cleanup procedure | Terraform state supports a scoped `terraform destroy` after testing. |

Network, IP-address, and account policies can vary by cloud account. Always inspect `terraform plan` before creating resources.

## Prerequisites

Install the following on the machine that will run Terraform:

- Terraform 1.6 or newer.
- At least one cloud provider account/project with permission to create the selected sandbox resources.
- Credentials for **only the provider you plan to enable**:
  - AWS: AWS CLI credentials (`aws configure`) or workload credentials.
  - Azure: authenticated Azure CLI session (`az login`) and an Azure subscription ID.
  - GCP: Application Default Credentials (`gcloud auth application-default login`) and a GCP project with Compute Engine API enabled.

Use a non-production cloud account, subscription, or project whenever possible.

## How to run Phase 2

Run all commands from the Terraform folder:

```powershell
cd D:\FinalYearProject\Cloud_Cost_Prediction_And_Optimization\infra\terraform
```

### 1. Create your local configuration

```powershell
Copy-Item terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars` is ignored by Git. It may contain subscription IDs, project IDs, and an SSH public key, so do not commit it.

### 2. Configure one cloud provider

Edit `terraform.tfvars` and enable **one** provider. For example, AWS:

```hcl
project_name       = "Clould_Cost_Prediction_And_Optimization"
environment        = "sandbox"
enable_aws         = true
aws_region         = "ap-south-1"
aws_create_compute = false
```

For Azure, provide a real `azure_subscription_id`. For GCP, provide a real `gcp_project_id`. Keep compute disabled until basic networking has been reviewed.

### 3. Authenticate with the chosen cloud

Use the provider-specific CLI, for example:

```powershell
# AWS
aws configure

# Azure
az login

# GCP
gcloud auth application-default login
```

Only authenticate to the provider selected in `terraform.tfvars`.

### 4. Initialize and check configuration

```powershell
terraform fmt -recursive -check
terraform init
terraform validate
```

`terraform init` downloads the locked provider plugins. `terraform validate` checks Terraform structure but does not create cloud resources.

### 5. Review the proposed change

```powershell
terraform plan -out=tfplan
```

Read the plan carefully. Confirm that it contains only the intended sandbox module and resources. If anything unexpected appears, do not apply it.

### 6. Create the approved sandbox (optional)

```powershell
terraform apply tfplan
```

This is the first command that can create cloud resources and incur cost. It is optional for Phase 2 validation, but needed if Phase 3 must ingest real sandbox data.

### 7. Read outputs

```powershell
terraform output
```

The command returns provider-specific IDs such as VPC/VNet/network, subnet, security group, resource group, and optional VM/EC2 identifiers. Phase 3 can use these IDs to verify adapter ingestion and resource discovery.

## Teardown after testing

When no longer needed, remove only the sandbox associated with the current Terraform state:

```powershell
terraform plan -destroy -out=destroy.tfplan
terraform apply destroy.tfplan
```

Do not run `terraform destroy` from a shared or production state. Verify the destroy plan carefully before applying it.

## What Phase 2 does not do

The following work belongs to later phases:

| Phase | Work not included in Phase 2 |
| --- | --- |
| Phase 3 | Provider SDK ingestion, normalized cost collection, FastAPI cost/resource routes |
| Phase 4 | Data preprocessing, Prophet forecasting, cost anomaly detection |
| Phase 5 | Streamlit dashboard and approval-controlled remediation endpoint |
| Phase 6 | Jenkins CI/CD, integration testing, deployment automation |

## Recommended next step

Continue with Phase 3. Start by implementing authenticated but read-only provider adapters, then build a scheduled ingestion worker that writes normalized cost and resource data into the PostgreSQL schema created in Phase 1.