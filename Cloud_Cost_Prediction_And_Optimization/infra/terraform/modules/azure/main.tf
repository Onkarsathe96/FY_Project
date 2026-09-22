resource "azurerm_resource_group" "sandbox" {
  name     = "${var.name_prefix}-rg"
  location = var.location
  tags     = var.common_tags
}

resource "azurerm_virtual_network" "sandbox" {
  name                = "${var.name_prefix}-vnet"
  address_space       = [var.vnet_cidr]
  location            = azurerm_resource_group.sandbox.location
  resource_group_name = azurerm_resource_group.sandbox.name
  tags                = var.common_tags
}

resource "azurerm_subnet" "sandbox" {
  name                 = "sandbox"
  resource_group_name  = azurerm_resource_group.sandbox.name
  virtual_network_name = azurerm_virtual_network.sandbox.name
  address_prefixes     = [cidrsubnet(var.vnet_cidr, 4, 0)]
}

resource "azurerm_network_security_group" "sandbox" {
  name                = "${var.name_prefix}-nsg"
  location            = azurerm_resource_group.sandbox.location
  resource_group_name = azurerm_resource_group.sandbox.name
  tags                = var.common_tags
}

resource "azurerm_network_interface" "sandbox" {
  count               = var.create_compute ? 1 : 0
  name                = "${var.name_prefix}-nic"
  location            = azurerm_resource_group.sandbox.location
  resource_group_name = azurerm_resource_group.sandbox.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.sandbox.id
    private_ip_address_allocation = "Dynamic"
  }
}

resource "azurerm_linux_virtual_machine" "sandbox" {
  count                           = var.create_compute ? 1 : 0
  name                            = "${var.name_prefix}-vm"
  resource_group_name             = azurerm_resource_group.sandbox.name
  location                        = azurerm_resource_group.sandbox.location
  size                            = "Standard_B1s"
  admin_username                  = var.admin_username
  network_interface_ids           = [azurerm_network_interface.sandbox[0].id]
  disable_password_authentication = true

  admin_ssh_key {
    username   = var.admin_username
    public_key = var.admin_ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }

  tags = var.common_tags

  lifecycle {
    precondition {
      condition     = var.admin_ssh_public_key != null && length(trimspace(var.admin_ssh_public_key)) > 0
      error_message = "azure_admin_ssh_public_key is required when Azure compute is enabled."
    }
  }
}