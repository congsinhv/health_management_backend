# Create secrets in Secret Manager
resource "google_secret_manager_secret" "secrets" {
  for_each = var.secrets

  # Replace underscores with hyphens for GCP naming requirements
  secret_id = "vhealth-${var.environment}-${replace(each.key, "_", "-")}"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Add secret versions
resource "google_secret_manager_secret_version" "secret_versions" {
  for_each = var.secrets

  secret      = google_secret_manager_secret.secrets[each.key].id
  secret_data = each.value != "" ? each.value : "placeholder"
}

# Grant Cloud Run service account access to secrets
resource "google_secret_manager_secret_iam_member" "secret_access" {
  for_each = var.secrets

  secret_id = google_secret_manager_secret.secrets[each.key].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.service_account_email}"
}
