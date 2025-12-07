# Enable Cloud Tasks API
resource "google_project_service" "cloudtasks" {
  service            = "cloudtasks.googleapis.com"
  disable_on_destroy = false
}

# Create Cloud Tasks queue
resource "google_cloud_tasks_queue" "queue" {
  name     = var.queue_name
  location = var.location
  project  = var.project_id

  rate_limits {
    max_dispatches_per_second = var.rate_limits.max_dispatches_per_second
    max_burst_size            = var.rate_limits.max_burst_size
    max_concurrent_dispatches = var.rate_limits.max_concurrent_dispatches
  }

  retry_config {
    max_attempts       = var.retry_config.max_attempts
    min_backoff        = var.retry_config.min_backoff
    max_backoff        = var.retry_config.max_backoff
    max_doublings      = var.retry_config.max_doublings
    max_retry_duration = var.retry_config.max_retry_duration
  }

  # Optional: Stack driver logging config
  dynamic "stackdriver_logging_config" {
    for_each = var.enable_logging ? [1] : []
    content {
      sampling_ratio = var.logging_sampling_ratio
    }
  }

  depends_on = [
    google_project_service.cloudtasks
  ]
}

# Service account for Cloud Tasks to invoke Cloud Run
resource "google_service_account" "cloudtasks_invoker" {
  count = var.create_service_account ? 1 : 0

  account_id   = var.service_account_id
  display_name = var.service_account_display_name
  description  = "Service account for Cloud Tasks to invoke Cloud Run endpoints via OIDC"
  project      = var.project_id

  depends_on = [google_project_service.cloudtasks]
}

# Grant Cloud Tasks enqueuer role to allow creating tasks
resource "google_project_iam_member" "cloudtasks_enqueuer" {
  count = var.create_service_account && var.grant_enqueuer_role ? 1 : 0

  project = var.project_id
  role    = "roles/cloudtasks.enqueuer"
  member  = "serviceAccount:${google_service_account.cloudtasks_invoker[0].email}"

  depends_on = [google_service_account.cloudtasks_invoker]
}

# Grant Cloud Run invoker role for OIDC authentication
resource "google_project_iam_member" "run_invoker" {
  count = var.create_service_account && var.grant_run_invoker_role ? 1 : 0

  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.cloudtasks_invoker[0].email}"

  depends_on = [google_service_account.cloudtasks_invoker]
}

# Grant service account token creator for OIDC token generation
resource "google_project_iam_member" "token_creator" {
  count = var.create_service_account && var.grant_token_creator_role ? 1 : 0

  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:${google_service_account.cloudtasks_invoker[0].email}"

  depends_on = [google_service_account.cloudtasks_invoker]
}

# Allow Cloud Run service account to create tasks in this queue
resource "google_cloud_tasks_queue_iam_member" "cloud_run_enqueuer" {
  count = var.cloud_run_service_account_email != null ? 1 : 0

  project  = var.project_id
  location = var.location
  name     = google_cloud_tasks_queue.queue.name
  role     = "roles/cloudtasks.enqueuer"
  member   = "serviceAccount:${var.cloud_run_service_account_email}"

  depends_on = [google_cloud_tasks_queue.queue]
}

