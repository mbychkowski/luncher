output "load_balancer_ip" {
  value       = google_compute_global_address.default.address
  description = "The reserved external IP address of the Global Load Balancer."
}

output "endpoint_hostname" {
  value       = google_endpoints_service.default.service_name
  description = "The Cloud Endpoints DNS hostname pointing to the Load Balancer."
}

output "endpoint_url" {
  value       = "https://${google_endpoints_service.default.service_name}"
  description = "The HTTPS URL to access the IAP-protected Cloud Run service."
}

output "backend_service_id" {
  value       = google_compute_backend_service.default.id
  description = "The ID of the GCLB backend service."
}
