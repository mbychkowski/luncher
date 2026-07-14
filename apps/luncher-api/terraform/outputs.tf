output "artifact_registry_repo" {
  value       = google_artifact_registry_repository.registry.name
  description = "The Artifact Registry repository name."
}

output "artifact_registry_location" {
  value       = google_artifact_registry_repository.registry.location
  description = "The location of the Artifact Registry repository."
}

output "cloud_run_url" {
  value       = google_cloud_run_v2_service.default.uri
  description = "The secure public URL of the deployed Cloud Run service."
}
