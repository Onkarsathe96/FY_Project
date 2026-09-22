variable "name_prefix" { type = string }
variable "location" { type = string }
variable "vnet_cidr" { type = string }
variable "create_compute" { type = bool }
variable "admin_username" { type = string }
variable "admin_ssh_public_key" {
  type      = string
  nullable  = true
  sensitive = true
}
variable "common_tags" { type = map(string) }