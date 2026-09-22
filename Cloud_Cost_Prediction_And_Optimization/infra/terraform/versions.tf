terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws     = { source = "hashicorp/aws", version = ">= 6.0, < 7.0" }
    azurerm = { source = "hashicorp/azurerm", version = ">= 4.0, < 6.0" }
    google  = { source = "hashicorp/google", version = ">= 7.0, < 8.0" }
    random  = { source = "hashicorp/random", version = "~> 3.7" }
  }
}
