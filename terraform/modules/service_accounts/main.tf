# Service accounts for VHealth microservices

# Main API Service Account - handles user requests and orchestrates other services
resource "google_service_account" "main_api" {
  account_id   = "${var.environment}-main-api-sa"
  display_name = "${var.title_case_environment} Main API Service Account"
  description  = "Service account for Main API microservice - handles user auth, CRUD operations, and service orchestration"
  project      = var.project_id
}

# Chat AI Service Account - handles Vietnamese Q&A and AI responses
resource "google_service_account" "chat_ai" {
  account_id   = "${var.environment}-chat-ai-sa"
  display_name = "${var.title_case_environment} Chat AI Service Account"
  description  = "Service account for Chat AI microservice - handles Vietnamese Q&A and AI-powered responses"
  project      = var.project_id
}

# Prediction Service Account - handles health predictions and recommendations
resource "google_service_account" "prediction" {
  account_id   = "${var.environment}-prediction-sa"
  display_name = "${var.title_case_environment} Prediction Service Account"
  description  = "Service account for Prediction microservice - handles health predictions and personalized recommendations"
  project      = var.project_id
}

# Grant Cloud SQL Client role to Main API (database owner)
resource "google_project_iam_member" "main_api_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.main_api.email}"
}

# Grant Cloud SQL Client role to Chat AI (read-only access)
resource "google_project_iam_member" "chat_ai_sql_client" {
  count   = var.enable_chat_ai_db_access ? 1 : 0
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.chat_ai.email}"
}

# Grant Cloud SQL Client role to Prediction (read-only access)
resource "google_project_iam_member" "prediction_sql_client" {
  count   = var.enable_prediction_db_access ? 1 : 0
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.prediction.email}"
}

# Grant Redis/Memorystore access to all services
resource "google_project_iam_member" "redis_access" {
  for_each = toset([
    google_service_account.main_api.email,
    google_service_account.chat_ai.email,
    google_service_account.prediction.email
  ])

  project = var.project_id
  role    = "roles/redis.editor"
  member  = "serviceAccount:${each.value}"
}

# Grant OpenAI API key access to AI services
resource "google_secret_manager_secret_iam_member" "openai_key_access" {
  for_each = toset([
    google_service_account.main_api.email,
    google_service_account.chat_ai.email,
    google_service_account.prediction.email
  ])

  secret_id = var.openai_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value}"
}

# Grant Secret Manager access for JWT secrets and other application secrets
resource "google_secret_manager_secret_iam_member" "app_secrets_access" {
  for_each = toset([
    google_service_account.main_api.email,
    google_service_account.chat_ai.email,
    google_service_account.prediction.email
  ])

  secret_id = var.app_secrets_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value}"
}

# Grant Cloud Storage access for model files and PDF storage
resource "google_project_iam_member" "storage_access" {
  for_each = toset([
    google_service_account.main_api.email,
    google_service_account.chat_ai.email,
    google_service_account.prediction.email
  ])

  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${each.value}"
}

# Grant Cloud Storage object admin to Main API for PDF uploads
resource "google_project_iam_member" "main_api_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.main_api.email}"
}

# Grant Cloud Run Invoker role to Main API for invoking other services
resource "google_cloud_run_service_iam_member" "main_api_invoker" {
  project  = var.project_id
  location = var.region
  service  = "${var.environment}-main-api"
  role     = "roles/run.invoker"
  member   = "allUsers"  # Public access for Main API
}

# Grant Logging and Monitoring permissions to all services
resource "google_project_iam_member" "logging_writer" {
  for_each = toset([
    google_service_account.main_api.email,
    google_service_account.chat_ai.email,
    google_service_account.prediction.email
  ])

  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${each.value}"
}

resource "google_project_iam_member" "monitoring_metric_writer" {
  for_each = toset([
    google_service_account.main_api.email,
    google_service_account.chat_ai.email,
    google_service_account.prediction.email
  ])

  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${each.value}"
}

# Grant Trace service agent for distributed tracing
resource "google_project_iam_member" "trace_agent" {
  for_each = toset([
    google_service_account.main_api.email,
    google_service_account.chat_ai.email,
    google_service_account.prediction.email
  ])

  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${each.value}"
}

# Grant Error Reporting permissions
resource "google_project_iam_member" "error_reporting_writer" {
  for_each = toset([
    google_service_account.main_api.email,
    google_service_account.chat_ai.email,
    google_service_account.prediction.email
  ])

  project = var.project_id
  role    = "roles/errorreporting.writer"
  member  = "serviceAccount:${each.value}"
}

# Enable service account impersonation for Main API
resource "google_service_account_iam_member" "main_api_impersonation" {
  service_account_id = google_service_account.main_api.name
  role              = "roles/iam.serviceAccountUser"
  member            = "serviceAccount:${google_service_account.main_api.email}"
}