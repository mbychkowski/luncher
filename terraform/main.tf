locals {
  project = {
    id     = var.project_id
    name   = data.google_project.project.name
    number = data.google_project.project.number
  }

  derived_domain = var.authorized_domain != "" ? var.authorized_domain : (
    var.iap_support_email != "" ? element(split("@", var.iap_support_email), 1) : ""
  )

  # Smart invoker member logic:
  # 1. If authorized_domain or iap_support_email is set, use "domain:<domain>"
  # 2. Otherwise use var.cloud_run_invoker_member (defaulting to "allUsers")
  effective_invoker_member = local.derived_domain != "" ? "domain:${local.derived_domain}" : var.cloud_run_invoker_member

  # Automatically grant roles/iap.httpsResourceAccessor to derived domain plus explicit iap_members
  effective_iap_members = distinct(concat(
    var.iap_members,
    local.derived_domain != "" ? ["domain:${local.derived_domain}"] : []
  ))
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
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

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

# Explicitly provision the IAP Service Identity
resource "google_project_service_identity" "iap_sa" {
  provider = google-beta
  project  = local.project.id
  service  = "iap.googleapis.com"
}

# Grant roles/run.invoker to the IAP Service Account on Cloud Run
resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  project  = local.project.id
  location = var.region
  name     = google_cloud_run_v2_service.default.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_project_service_identity.iap_sa.email}"
}

# Grant roles/aiplatform.user to Vertex AI Reasoning Engine Service Identity
resource "google_project_iam_member" "aiplatform_sa_user" {
  project    = local.project.id
  role       = "roles/aiplatform.user"
  member     = "serviceAccount:${google_project_service_identity.aiplatform_sa.email}"
  depends_on = [google_project_service_identity.aiplatform_sa]
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

# Grant roles/storage.objectViewer to Compute Service Account project-wide (required for Cloud Build source retrieval)
resource "google_project_iam_member" "compute_sa_storage_viewer" {
  project = local.project.id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

# Grant roles/logging.logWriter to Compute Service Account (Cloud Run)
resource "google_project_iam_member" "compute_sa_log_writer" {
  project = local.project.id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

# Grant Artifact Registry Reader to Compute Default Service Account (used by Cloud Run to pull images)
resource "google_artifact_registry_repository_iam_member" "compute_sa_ar_reader" {
  project    = local.project.id
  location   = var.region
  repository = google_artifact_registry_repository.registry.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

# Grant Artifact Registry Writer to Compute Default Service Account (used by Cloud Build to push images)
resource "google_artifact_registry_repository_iam_member" "compute_sa_ar_writer" {
  project    = local.project.id
  location   = var.region
  repository = google_artifact_registry_repository.registry.name
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

# Optional: Override domain-restricted sharing if Org Policy blocks allUsers
resource "google_project_organization_policy" "disable_domain_restriction" {
  count      = var.override_domain_restriction ? 1 : 0
  project    = local.project.id
  constraint = "constraints/iam.allowedPolicyMemberDomains"

  list_policy {
    allow {
      all = true
    }
  }
}

# Allow Load Balancer access to Cloud Run (IAP enforces authentication at GCLB)
resource "google_cloud_run_v2_service_iam_member" "lb_invoker" {
  count    = local.effective_invoker_member != "" ? 1 : 0
  project  = local.project.id
  location = var.region
  name     = google_cloud_run_v2_service.default.name
  role     = "roles/run.invoker"
  member   = local.effective_invoker_member

  depends_on = [google_project_organization_policy.disable_domain_restriction]
}

# -----------------------------------------------------------------
# GLOBAL HTTP(S) LOAD BALANCER + IAP + CLOUD ENDPOINTS MODULE
# -----------------------------------------------------------------
module "iap_gclb" {
  count                  = (var.iap_client_id != "" || var.iap_support_email != "") ? 1 : 0
  source                 = "./modules/iap_gclb"
  project_id             = local.project.id
  region                 = var.region
  name_prefix            = "luncher"
  dns_prefix             = "luncher"
  cloud_run_service_name = google_cloud_run_v2_service.default.name
  iap_client_id          = var.iap_client_id
  iap_client_secret      = var.iap_client_secret
  support_email          = var.iap_support_email
  enable_brand_creation  = var.enable_brand_creation
  iap_members            = local.effective_iap_members
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
