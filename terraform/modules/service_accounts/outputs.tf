output "main_api_email" {
  description = "Main API service account email"
  value       = google_service_account.main_api.email
}

output "main_api_name" {
  description = "Main API service account name"
  value       = google_service_account.main_api.name
}

output "main_api_id" {
  description = "Main API service account ID"
  value       = google_service_account.main_api.account_id
}

output "chat_ai_email" {
  description = "Chat AI service account email"
  value       = google_service_account.chat_ai.email
}

output "chat_ai_name" {
  description = "Chat AI service account name"
  value       = google_service_account.chat_ai.name
}

output "chat_ai_id" {
  description = "Chat AI service account ID"
  value       = google_service_account.chat_ai.account_id
}

output "prediction_email" {
  description = "Prediction service account email"
  value       = google_service_account.prediction.email
}

output "prediction_name" {
  description = "Prediction service account name"
  value       = google_service_account.prediction.name
}

output "prediction_id" {
  description = "Prediction service account ID"
  value       = google_service_account.prediction.account_id
}

output "all_service_accounts" {
  description = "All service account emails"
  value = {
    main_api   = google_service_account.main_api.email
    chat_ai    = google_service_account.chat_ai.email
    prediction = google_service_account.prediction.email
  }
}

output "service_account_details" {
  description = "Detailed service account information"
  value = {
    main_api = {
      email      = google_service_account.main_api.email
      account_id = google_service_account.main_api.account_id
      name       = google_service_account.main_api.display_name
      roles = [
        "roles/cloudsql.client",
        "roles/redis.editor",
        "roles/secretmanager.secretAccessor",
        "roles/storage.objectAdmin",
        "roles/logging.logWriter",
        "roles/monitoring.metricWriter",
        "roles/cloudtrace.agent",
        "roles/errorreporting.writer"
      ]
    }
    chat_ai = {
      email      = google_service_account.chat_ai.email
      account_id = google_service_account.chat_ai.account_id
      name       = google_service_account.chat_ai.display_name
      roles = var.enable_chat_ai_db_access ? [
        "roles/cloudsql.client",
        "roles/redis.editor",
        "roles/secretmanager.secretAccessor",
        "roles/storage.objectViewer",
        "roles/logging.logWriter",
        "roles/monitoring.metricWriter",
        "roles/cloudtrace.agent",
        "roles/errorreporting.writer"
      ] : [
        "roles/redis.editor",
        "roles/secretmanager.secretAccessor",
        "roles/storage.objectViewer",
        "roles/logging.logWriter",
        "roles/monitoring.metricWriter",
        "roles/cloudtrace.agent",
        "roles/errorreporting.writer"
      ]
    }
    prediction = {
      email      = google_service_account.prediction.email
      account_id = google_service_account.prediction.account_id
      name       = google_service_account.prediction.display_name
      roles = var.enable_prediction_db_access ? [
        "roles/cloudsql.client",
        "roles/redis.editor",
        "roles/secretmanager.secretAccessor",
        "roles/storage.objectViewer",
        "roles/logging.logWriter",
        "roles/monitoring.metricWriter",
        "roles/cloudtrace.agent",
        "roles/errorreporting.writer"
      ] : [
        "roles/redis.editor",
        "roles/secretmanager.secretAccessor",
        "roles/storage.objectViewer",
        "roles/logging.logWriter",
        "roles/monitoring.metricWriter",
        "roles/cloudtrace.agent",
        "roles/errorreporting.writer"
      ]
    }
  }
}