variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "asia-southeast1"
}

variable "title_case_environment" {
  description = "Environment name with title case (Development/Production)"
  type        = string
  default     = "Development"
}

variable "openai_secret_id" {
  description = "Secret Manager secret ID for OpenAI API key"
  type        = string
}

variable "app_secrets_id" {
  description = "Secret Manager secret ID for application secrets (JWT, etc.)"
  type        = string
}

variable "enable_chat_ai_db_access" {
  description = "Enable direct database access for Chat AI service"
  type        = bool
  default     = false
}

variable "enable_prediction_db_access" {
  description = "Enable direct database access for Prediction service"
  type        = bool
  default     = false
}