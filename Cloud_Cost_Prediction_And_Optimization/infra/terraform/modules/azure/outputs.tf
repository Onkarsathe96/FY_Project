output "resource_group_name" { value = azurerm_resource_group.sandbox.name }
output "vnet_id" { value = azurerm_virtual_network.sandbox.id }
output "subnet_id" { value = azurerm_subnet.sandbox.id }
output "vm_id" { value = try(azurerm_linux_virtual_machine.sandbox[0].id, null) }
