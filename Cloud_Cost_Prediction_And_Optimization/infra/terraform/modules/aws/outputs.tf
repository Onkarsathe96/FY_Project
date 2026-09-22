output "vpc_id" { value = aws_vpc.sandbox.id }
output "subnet_id" { value = aws_subnet.sandbox.id }
output "security_group_id" { value = aws_security_group.sandbox.id }
output "instance_id" { value = try(aws_instance.sandbox[0].id, null) }
