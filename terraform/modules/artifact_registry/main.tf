resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = var.repository_id
  description   = "Docker repository for ${var.environment} environment"
  format        = "DOCKER"

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# IAM binding to allow Cloud Run to pull images
resource "google_artifact_registry_repository_iam_member" "cloud_run_pull" {
  project    = var.project_id
  location   = google_artifact_registry_repository.docker_repo.location
  repository = google_artifact_registry_repository.docker_repo.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${var.service_account_email}"
}
