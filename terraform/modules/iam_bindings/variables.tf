variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
}

variable "main_api_sa_email" {
  description = "Main API service account email"
  type        = string
}

variable "chat_ai_sa_email" {
  description = "Chat AI service account email"
  type        = string
}

variable "prediction_sa_email" {
  description = "Prediction service account email"
  type        = string
}

variable "main_api_service_name" {
  description = "Main API Cloud Run service name"
  type        = string
}

variable "chat_ai_service_name" {
  description = "Chat AI Cloud Run service name"
  type        = string
}

variable "prediction_service_name" {
  description = "Prediction Cloud Run service name"
  type        = string
}

variable "enable_reverse_communication" {
  description = "Enable AI services to call back to Main API"
  type        = bool
  default     = false
}

variable "enable_debug_access" {
  description = "Enable debug access for service accounts"
  type        = bool
  default     = false
}

variable "enable_time_restrictions" {
  description = "Enable time-based access restrictions for public API"
  type        = bool
  default     = false
}

# Service dependencies to ensure proper ordering
variable "main_api_service_dependency" {
  description = "Main API service resource for dependency"
  type        = any
  default     = null
}

variable "chat_ai_service_dependency" {
  description = "Chat AI service resource for dependency"
  type        = any
  default     = null
}

variable "prediction_service_dependency" {
  description = "Prediction service resource for dependency"
  type        = any
  default     = null
}