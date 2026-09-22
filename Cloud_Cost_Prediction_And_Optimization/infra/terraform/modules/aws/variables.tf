variable "name_prefix" { type = string }
variable "vpc_cidr" { type = string }
variable "create_compute" { type = bool }
variable "common_tags" { type = map(string) }
