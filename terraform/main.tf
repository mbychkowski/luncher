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
      resources {
        limits = {
          memory = "1Gi"
        }
      }

      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = local.project.id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "STRATEGY_DOCS_BUCKET"
        value = google_storage_bucket.strategy_docs.name
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
    ignore_changes = [
      template[0].containers[0].image
    ]
  }
}

# Cloud Run service invoker permissions (domain-restricted when authorized_domain is set)
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  project  = local.project.id
  location = google_cloud_run_v2_service.default.location
  name     = google_cloud_run_v2_service.default.name
  role     = "roles/run.invoker"
  member   = var.authorized_domain != null && var.authorized_domain != "" ? "domain:${var.authorized_domain}" : "allUsers"
}

# Google Cloud Storage bucket for strategy PDF documents
resource "google_storage_bucket" "strategy_docs" {
  name          = "luncher-strategy-docs-${local.project.id}"
  location      = var.region
  project       = local.project.id
  force_destroy = true

  uniform_bucket_level_access = true
}

# Explicitly provision the Vertex AI Service Identity
resource "google_project_service_identity" "aiplatform_sa" {
  provider = google-beta
  project  = local.project.id
  service  = "aiplatform.googleapis.com"
}

# Grant roles/storage.objectViewer to the AI Platform Reasoning Engine Service Agent on the bucket
resource "google_storage_bucket_iam_member" "agent_docs_viewer" {
  bucket     = google_storage_bucket.strategy_docs.name
  role       = "roles/storage.objectViewer"
  member     = "serviceAccount:${google_project_service_identity.aiplatform_sa.email}"
  depends_on = [google_project_service_identity.aiplatform_sa]
}

# Grant roles/storage.objectViewer to Compute Service Account (Cloud Run)
resource "google_storage_bucket_iam_member" "compute_sa_docs_viewer" {
  bucket = google_storage_bucket.strategy_docs.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

# Codify Vertex AI Gemini 2.5 Flash RPM Quota Preference
resource "google_cloud_quotas_quota_preference" "gemini_2_5_flash_quota" {
  parent        = "projects/${local.project.id}"
  name          = "gemini-2-5-flash-rpm-quota"
  service       = "aiplatform.googleapis.com"
  quota_id      = "GenerateContentRequestsPerMinutePerProjectPerRegionPerBaseModel"
  contact_email = var.contact_email

  dimensions = {
    region     = var.region
    base_model = "gemini-2.5-flash"
  }

  quota_config {
    preferred_value = 300
  }
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
