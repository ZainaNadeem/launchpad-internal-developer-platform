data "aws_iam_policy_document" "platform_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "platform" {
  name               = "${var.project_name}-${var.environment}-platform-role"
  assume_role_policy = data.aws_iam_policy_document.platform_assume_role.json

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}