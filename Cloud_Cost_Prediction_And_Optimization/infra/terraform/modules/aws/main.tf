data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_ami" "amazon_linux" {
  count       = var.create_compute ? 1 : 0
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }
}

resource "aws_vpc" "sandbox" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  tags                 = merge(var.common_tags, { Name = "${var.name_prefix}-vpc" })
}

resource "aws_subnet" "sandbox" {
  vpc_id                  = aws_vpc.sandbox.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, 0)
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = false
  tags                    = merge(var.common_tags, { Name = "${var.name_prefix}-subnet" })
}

resource "aws_security_group" "sandbox" {
  name_prefix = "${var.name_prefix}-sg-"
  description = "Cloud cost prediction Phase 2 sandbox: no inbound access"
  vpc_id      = aws_vpc.sandbox.id
  tags        = merge(var.common_tags, { Name = "${var.name_prefix}-sg" })

  egress {
    description = "HTTPS only"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "sandbox" {
  count                       = var.create_compute ? 1 : 0
  ami                         = data.aws_ami.amazon_linux[0].id
  instance_type               = "t3.micro"
  subnet_id                   = aws_subnet.sandbox.id
  vpc_security_group_ids      = [aws_security_group.sandbox.id]
  associate_public_ip_address = false
  monitoring                  = true
  tags                        = merge(var.common_tags, { Name = "${var.name_prefix}-ec2" })
}