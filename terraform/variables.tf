variable "project_id" {
  type        = string
  description = "The Google Cloud project ID to deploy resources to."
}

variable "region" {
  type        = string
  description = "The primary region for Google Cloud resource deployments."
  default     = "us-central1"
}

variable "image_url" {
  type        = string
  description = "The container image URL to deploy to Cloud Run."
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}
