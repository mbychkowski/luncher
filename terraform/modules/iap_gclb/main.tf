# Ensure required APIs are enabled before creating IAP, GCLB, or Cloud Endpoints resources
resource "google_project_service" "iap" {
  project            = var.project_id
  service            = "iap.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "endpoints" {
  project            = var.project_id
  service            = "endpoints.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "servicemanagement" {
  project            = var.project_id
  service            = "servicemanagement.googleapis.com"
  disable_on_destroy = false
}

# Auto-provision IAP OAuth Brand if support_email is provided, iap_client_id is omitted, and enable_brand_creation is true
resource "google_iap_brand" "project_brand" {
  count             = var.enable_brand_creation && var.iap_client_id == "" && var.support_email != "" ? 1 : 0
  support_email     = var.support_email
  application_title = "${var.name_prefix} Application"
  project           = var.project_id

  depends_on = [google_project_service.iap]
}

# Auto-provision IAP OAuth Client ID and Secret
resource "google_iap_client" "project_client" {
  count        = var.enable_brand_creation && var.iap_client_id == "" && var.support_email != "" ? 1 : 0
  display_name = "${var.name_prefix}-iap-client"
  brand        = google_iap_brand.project_brand[0].name
}

locals {
  effective_client_id     = var.iap_client_id != "" ? var.iap_client_id : (length(google_iap_client.project_client) > 0 ? google_iap_client.project_client[0].client_id : "")
  effective_client_secret = var.iap_client_secret != "" ? var.iap_client_secret : (length(google_iap_client.project_client) > 0 ? google_iap_client.project_client[0].secret : "")
}

# 1. Global External IP Address
resource "google_compute_global_address" "default" {
  name    = "${var.name_prefix}-lb-ip"
  project = var.project_id
}

# 2. Cloud Endpoints Service for Free Managed DNS (*.endpoints.<project_id>.cloud.goog)
resource "google_endpoints_service" "default" {
  service_name   = "${var.dns_prefix}.${var.project_id}.endpoints.${var.project_id}.cloud.goog"
  project        = var.project_id
  grpc_config    = null
  openapi_config = <<EOF
swagger: "2.0"
info:
  description: "Cloud Endpoints managed DNS for ${var.name_prefix}"
  title: "${var.name_prefix}-endpoints"
  version: "1.0.0"
host: "${var.dns_prefix}.${var.project_id}.endpoints.${var.project_id}.cloud.goog"
x-google-endpoints:
- name: "${var.dns_prefix}.${var.project_id}.endpoints.${var.project_id}.cloud.goog"
  target: "${google_compute_global_address.default.address}"
paths: {}
EOF

  depends_on = [
    google_compute_global_address.default,
    google_project_service.endpoints,
    google_project_service.servicemanagement
  ]
}

# 3. Managed SSL Certificate for Cloud Endpoints Domain
resource "google_compute_managed_ssl_certificate" "default" {
  name    = "${var.name_prefix}-ssl-cert"
  project = var.project_id

  managed {
    domains = [google_endpoints_service.default.service_name]
  }
}

# 4. Serverless Network Endpoint Group (NEG) pointing to Cloud Run
resource "google_compute_region_network_endpoint_group" "cloudrun_neg" {
  name                  = "${var.name_prefix}-neg"
  project               = var.project_id
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = var.cloud_run_service_name
  }
}

# 5. Global Backend Service with IAP Enabled
resource "google_compute_backend_service" "default" {
  name                  = "${var.name_prefix}-backend-service"
  project               = var.project_id
  protocol              = "HTTPS"
  port_name             = "http"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.cloudrun_neg.id
  }

  iap {
    oauth2_client_id     = local.effective_client_id
    oauth2_client_secret = local.effective_client_secret
  }
}

# 6. URL Map
resource "google_compute_url_map" "default" {
  name            = "${var.name_prefix}-url-map"
  project         = var.project_id
  default_service = google_compute_backend_service.default.id
}

# 7. Target HTTPS Proxy
resource "google_compute_target_https_proxy" "default" {
  name             = "${var.name_prefix}-https-proxy"
  project          = var.project_id
  url_map          = google_compute_url_map.default.id
  ssl_certificates = [google_compute_managed_ssl_certificate.default.id]
}

# 8. Global Forwarding Rule for HTTPS (Port 443)
resource "google_compute_global_forwarding_rule" "https" {
  name                  = "${var.name_prefix}-https-fw"
  project               = var.project_id
  target                = google_compute_target_https_proxy.default.id
  port_range            = "443"
  ip_address            = google_compute_global_address.default.address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# 9. Optional HTTP (Port 80) to HTTPS Redirect
resource "google_compute_url_map" "http_redirect" {
  count   = var.enable_http_redirect ? 1 : 0
  name    = "${var.name_prefix}-http-redirect"
  project = var.project_id

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "http_redirect" {
  count   = var.enable_http_redirect ? 1 : 0
  name    = "${var.name_prefix}-http-proxy"
  project = var.project_id
  url_map = google_compute_url_map.http_redirect[0].id
}

resource "google_compute_global_forwarding_rule" "http_redirect" {
  count                 = var.enable_http_redirect ? 1 : 0
  name                  = "${var.name_prefix}-http-fw"
  project               = var.project_id
  target                = google_compute_target_http_proxy.http_redirect[0].id
  port_range            = "80"
  ip_address            = google_compute_global_address.default.address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# 10. Grant IAP Access to Authorized Members
resource "google_iap_web_backend_service_iam_member" "users" {
  for_each            = toset(var.iap_members)
  project             = var.project_id
  web_backend_service = google_compute_backend_service.default.name
  role                = "roles/iap.httpsResourceAccessor"
  member              = each.value
}
