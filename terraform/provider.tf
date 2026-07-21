terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.40.0"
    }
  }

  backend "gcs" {
    # Backend bucket is configured dynamically during 'terraform init' in GitHub Actions 
    # via the -backend-config="bucket=..." flag.
  }
}

provider "google" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

provider "google-beta" {
  project               = var.project_id
  region                = var.region
  user_project_override = true
  billing_project       = var.project_id
}

