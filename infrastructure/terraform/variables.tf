variable "aws_region" {
  description = "AWS region for LaunchPad infrastructure"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Name used to identify LaunchPad resources"
  type        = string
  default     = "launchpad"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"
}

variable "vpc_cidr" {
  description = "CIDR range assigned to the LaunchPad VPC"
  type        = string
  default     = "10.0.0.0/16"
}