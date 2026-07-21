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

variable "contact_email" {
  type        = string
  description = "Contact email address for quota preference increase requests."
  default     = null
}

variable "authorized_domain" {
  type        = string
  description = "The Google Workspace or Cloud Identity domain authorized to invoke Cloud Run."
  default     = null
}


