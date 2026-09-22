variable "name_prefix" { type = string }
variable "region" { type = string }
variable "zone" { type = string }
variable "subnet_cidr" { type = string }
variable "create_compute" { type = bool }
variable "labels" { type = map(string) }
