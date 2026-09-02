output "vpc_id" {
  description = "ID of the LaunchPad VPC"
  value       = aws_vpc.launchpad.id
}

output "vpc_cidr" {
  description = "CIDR range of the LaunchPad VPC"
  value       = aws_vpc.launchpad.cidr_block
}