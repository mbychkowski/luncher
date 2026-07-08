locals {
  project = {
    id     = var.project_id
    name   = data.google_project.project.name
    number = data.google_project.project.number
  }
}

data "google_project" "project" {
  project_id = var.project_id
}

# Artifact Registry repository for storing docker images
resource "google_artifact_registry_repository" "registry" {
  location      = var.region
  repository_id = "luncher-repo"
  description   = "Docker registry for luncher container images"
  format        = "DOCKER"
  project       = local.project.id
}

# Cloud Run service managed fully by Terraform
resource "google_cloud_run_v2_service" "default" {
  name     = "luncher-service"
  location = var.region
  project  = local.project.id
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    containers {
      image = var.image_url
      ports {
        container_port = 8080
      }

      # -----------------------------------------------------------------
      # OPTIONAL: MOUNT SECRET MANAGER SECRETS TO ENVIRONMENT VARIABLES
      # To use this, uncomment the blocks below and create the secret resources.
      # -----------------------------------------------------------------
      # env {
      #   name = "DATABASE_API_KEY"
      #   value_source {
      #     secret_key_ref {
      #       secret  = google_secret_manager_secret.api_key[0].secret_id
      #       version = "latest"
      #     }
      #   }
      # }
    }
  }

  lifecycle {
    # This prevents Terraform from reverting the image back to the placeholder if updated out-of-band
    ignore_changes = []
  }
}

# Make the Cloud Run service publicly accessible (unauthenticated)
resource "google_cloud_run_v2_service_iam_member" "noauth" {
  project  = local.project.id
  location = google_cloud_run_v2_service.default.location
  name     = google_cloud_run_v2_service.default.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# -----------------------------------------------------------------
# OPTIONAL TEMPLATE: GOOGLE SECRET MANAGER RESOURCE DEFINITIONS
# Uncomment the block below to automatically provision secrets in GCP
# -----------------------------------------------------------------
# resource "google_secret_manager_secret" "api_key" {
#   count     = 0 # Set to 1 to enable
#   project   = local.project.id
#   secret_id = "luncher-api-key"
#
#   replication {
#     auto {}
#   }
# }
#
# # Allow Cloud Run's Service Account (or default compute service account) to read the secret
# resource "google_secret_manager_secret_iam_member" "api_key_accessor" {
#   count     = 0 # Set to 1 to enable
#   project   = local.project.id
#   secret_id = google_secret_manager_secret.api_key[0].secret_id
#   role      = "roles/secretmanager.secretAccessor"
#   member    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
# }
