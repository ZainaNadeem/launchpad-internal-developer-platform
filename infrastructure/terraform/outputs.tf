output "vpc_id" {
  description = "ID of the LaunchPad VPC"
  value       = aws_vpc.launchpad.id
}

output "vpc_cidr" {
  description = "CIDR range of the LaunchPad VPC"
  value       = aws_vpc.launchpad.cidr_block
}

output "public_subnet_id" {
  description = "ID of the LaunchPad public subnet"
  value       = aws_subnet.public.id
}

output "private_subnet_id" {
  description = "ID of the LaunchPad private subnet"
  value       = aws_subnet.private.id
}

output "platform_security_group_id" {
  description = "Security group for LaunchPad platform workloads"
  value       = aws_security_group.platform.id
}

output "platform_role_name" {
  description = "IAM role for LaunchPad platform workloads"
  value       = aws_iam_role.platform.name
}