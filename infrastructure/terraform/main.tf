terraform {
  required_version = ">= 1.5.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

provider "local" {}

resource "local_file" "launchpad_metadata" {
  filename = "${path.module}/launchpad-generated.txt"

  content = <<-EOT
  project=LaunchPad
  managed_by=Terraform
  purpose=Internal Developer Platform
  EOT
}