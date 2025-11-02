# Enable Cloud Scheduler API
resource "google_project_service" "scheduler" {
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

# Create Cloud Scheduler job
resource "google_cloud_scheduler_job" "job" {
  name             = var.job_name
  description      = var.description
  schedule         = var.schedule
  time_zone        = var.time_zone
  region           = var.region
  attempt_deadline = var.attempt_deadline
  paused           = var.paused

  retry_config {
    retry_count          = var.retry_config.retry_count
    max_retry_duration   = var.retry_config.max_retry_duration
    min_backoff_duration = var.retry_config.min_backoff_duration
    max_backoff_duration = var.retry_config.max_backoff_duration
    max_doublings        = var.retry_config.max_doublings
  }

  http_target {
    uri         = var.http_target_uri
    http_method = var.http_method
    body        = var.http_body
    headers     = var.http_headers

    # OIDC token for authenticated endpoints (e.g., Cloud Run with authentication)
    dynamic "oidc_token" {
      for_each = var.oidc_token && var.service_account_email != null ? [1] : []
      content {
        service_account_email = var.service_account_email
      }
    }
  }

  depends_on = [
    google_project_service.scheduler
  ]
}

# Grant Cloud Scheduler permission to invoke Cloud Run (if using OIDC)
resource "google_cloud_run_service_iam_member" "scheduler_invoker" {
  count = var.oidc_token && var.service_account_email != null ? 1 : 0

  # Extract service name and location from the URI
  # This assumes URI format: https://SERVICE_NAME-PROJECT_ID.REGION.run.app/path
  service  = split("-", split(".", split("//", var.http_target_uri)[1])[0])[0]
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.service_account_email}"

  depends_on = [google_cloud_scheduler_job.job]
}

