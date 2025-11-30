# IAM bindings for service-to-service communication

# Main API can invoke Chat AI service
resource "google_cloud_run_service_iam_member" "main_api_to_chat_ai" {
  project  = var.project_id
  location = var.region
  service  = var.chat_ai_service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.main_api_sa_email}"

  depends_on = [var.chat_ai_service_dependency]
}

# Main API can invoke Prediction service
resource "google_cloud_run_service_iam_member" "main_api_to_prediction" {
  project  = var.project_id
  location = var.region
  service  = var.prediction_service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.main_api_sa_email}"

  depends_on = [var.prediction_service_dependency]
}

# Allow public access to Main API (external users)
resource "google_cloud_run_service_iam_member" "main_api_public" {
  project  = var.project_id
  location = var.region
  service  = var.main_api_service_name
  role     = "roles/run.invoker"
  member   = "allUsers"

  depends_on = [var.main_api_service_dependency]
}

# Service-to-service communication with least privilege
# Grant Chat AI service permission to access Main API (for health checks, callbacks)
resource "google_cloud_run_service_iam_member" "chat_ai_to_main_api" {
  count    = var.enable_reverse_communication ? 1 : 0
  project  = var.project_id
  location = var.region
  service  = var.main_api_service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.chat_ai_sa_email}"

  depends_on = [var.main_api_service_dependency]
}

# Grant Prediction service permission to access Main API (for health checks, callbacks)
resource "google_cloud_run_service_iam_member" "prediction_to_main_api" {
  count    = var.enable_reverse_communication ? 1 : 0
  project  = var.project_id
  location = var.region
  service  = var.main_api_service_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.prediction_sa_email}"

  depends_on = [var.main_api_service_dependency]
}

# Grant Cloud Run Developer role to main service account for service management
resource "google_cloud_run_service_iam_member" "main_api_developer" {
  project  = var.project_id
  location = var.region
  service  = var.main_api_service_name
  role     = "roles/run.developer"
  member   = "serviceAccount:${var.main_api_sa_email}"
}

# Grant Cloud Run Developer role to chat AI service account for its own service management
resource "google_cloud_run_service_iam_member" "chat_ai_developer" {
  project  = var.project_id
  location = var.region
  service  = var.chat_ai_service_name
  role     = "roles/run.developer"
  member   = "serviceAccount:${var.chat_ai_sa_email}"
}

# Grant Cloud Run Developer role to prediction service account for its own service management
resource "google_cloud_run_service_iam_member" "prediction_developer" {
  project  = var.project_id
  location = var.region
  service  = var.prediction_service_name
  role     = "roles/run.developer"
  member   = "serviceAccount:${var.prediction_sa_email}"
}

# Grant Viewer role to all services for monitoring purposes
resource "google_cloud_run_service_iam_member" "main_api_viewer" {
  project  = var.project_id
  location = var.region
  service  = var.main_api_service_name
  role     = "roles/viewer"
  member   = "serviceAccount:${var.main_api_sa_email}"
}

# Optional: Grant additional roles for debugging and troubleshooting
resource "google_cloud_run_service_iam_member" "main_api_debugger" {
  count    = var.enable_debug_access ? 1 : 0
  project  = var.project_id
  location = var.region
  service  = var.main_api_service_name
  role     = "roles/run.admin"
  member   = "serviceAccount:${var.main_api_sa_email}"
}

# IAM policy for logging and monitoring access
resource "google_cloud_run_service_iam_member" "main_api_logging" {
  project  = var.project_id
  location = var.region
  service  = var.main_api_service_name
  role     = "roles/logging.viewer"
  member   = "serviceAccount:${var.main_api_sa_email}"
}

# Custom IAM conditions for time-based access (optional)
resource "google_cloud_run_service_iam_member" "main_api_time_restricted" {
  count    = var.enable_time_restrictions ? 1 : 0
  project  = var.project_id
  location = var.region
  service  = var.main_api_service_name
  role     = "roles/run.invoker"
  member   = "allUsers"
  condition {
    title       = "Time-based access restriction"
    description = "Allow public access only during business hours"
    expression   = "request.time.getHours() >= 6 && request.time.getHours() <= 22"
  }
}