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

variable "authorized_domain" {
  type        = string
  description = "Organization domain (e.g. mbychkowski.altostrat.com) granted roles/run.invoker on Cloud Run when domain restrictions are active."
  default     = ""
}

variable "iap_client_id" {
  type        = string
  description = "OAuth 2.0 Client ID for Identity-Aware Proxy."
  sensitive   = true
  default     = ""
}

variable "iap_client_secret" {
  type        = string
  description = "OAuth 2.0 Client Secret for Identity-Aware Proxy."
  sensitive   = true
  default     = ""
}

variable "iap_support_email" {
  type        = string
  description = "Support email used to auto-provision an IAP OAuth Brand & Client ID if iap_client_id is empty."
  default     = ""
}

variable "iap_members" {
  type        = list(string)
  description = "List of IAM members granted iap.httpsResourceAccessor role (e.g. user:name@example.com)."
  default     = []
}

variable "cloud_run_invoker_member" {
  type        = string
  description = "IAM member granted roles/run.invoker on Cloud Run (default: allUsers). Use domain:example.com or user:email@example.com if org policy blocks allUsers."
  default     = "allUsers"
}

variable "override_domain_restriction" {
  type        = bool
  description = "Set to true to disable constraints/iam.allowedPolicyMemberDomains on the project if Org Policy blocks allUsers."
  default     = false
}

variable "enable_brand_creation" {
  type        = bool
  description = "Set to true to attempt programmatic creation of IAP OAuth Brand (Note: Google turned down programmatic OAuth Brand creation for new projects in Jan 2026; set to false and pass iap_client_id/iap_client_secret instead)."
  default     = false
}
