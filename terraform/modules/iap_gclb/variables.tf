variable "project_id" {
  type        = string
  description = "The GCP project ID."
}

variable "region" {
  type        = string
  description = "The GCP region where Cloud Run is deployed."
}

variable "name_prefix" {
  type        = string
  description = "Prefix for naming Load Balancer and Endpoints resources."
  default     = "luncher"
}

variable "dns_prefix" {
  type        = string
  description = "DNS prefix for the Cloud Endpoints domain (<dns_prefix>.<project_id>.endpoints.<project_id>.cloud.goog)."
  default     = "luncher"
}

variable "cloud_run_service_name" {
  type        = string
  description = "The name of the target Cloud Run v2 service."
}

variable "iap_client_id" {
  type        = string
  description = "OAuth 2.0 Client ID for Identity-Aware Proxy (IAP)."
  sensitive   = true
  default     = ""
}

variable "iap_client_secret" {
  type        = string
  description = "OAuth 2.0 Client Secret for Identity-Aware Proxy (IAP)."
  sensitive   = true
  default     = ""
}

variable "support_email" {
  type        = string
  description = "Support email used to automatically create IAP OAuth Brand & Client if iap_client_id is omitted."
  default     = ""
}

variable "enable_brand_creation" {
  type        = bool
  description = "Set to true to attempt programmatic creation of IAP OAuth Brand (Note: Google turned down programmatic OAuth Brand creation for new projects in Jan 2026; set to false and pass iap_client_id/iap_client_secret instead)."
  default     = false
}

variable "iap_members" {
  type        = list(string)
  description = "List of IAM members (e.g. user:email@example.com, group:team@example.com, domain:example.com) granted iap.httpsResourceAccessor role."
  default     = []
}

variable "enable_http_redirect" {
  type        = bool
  description = "Whether to enable HTTP to HTTPS redirect on port 80."
  default     = true
}
