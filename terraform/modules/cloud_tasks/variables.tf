variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "location" {
  description = "GCP region for Cloud Tasks queue"
  type        = string
}

variable "queue_name" {
  description = "Name of the Cloud Tasks queue"
  type        = string
}

variable "rate_limits" {
  description = "Rate limits configuration for the queue"
  type = object({
    max_dispatches_per_second = optional(number, 500)
    max_burst_size            = optional(number, 100)
    max_concurrent_dispatches = optional(number, 1000)
  })
  default = {
    max_dispatches_per_second = 500
    max_burst_size            = 100
    max_concurrent_dispatches = 1000
  }
}

variable "retry_config" {
  description = "Retry configuration for failed tasks"
  type = object({
    max_attempts       = optional(number, 3)
    min_backoff        = optional(string, "1s")
    max_backoff        = optional(string, "3600s")
    max_doublings      = optional(number, 16)
    max_retry_duration = optional(string, "0s")
  })
  default = {
    max_attempts       = 3
    min_backoff        = "1s"
    max_backoff        = "3600s"
    max_doublings      = 16
    max_retry_duration = "0s"
  }
}

variable "enable_logging" {
  description = "Enable Stackdriver logging for the queue"
  type        = bool
  default     = true
}

variable "logging_sampling_ratio" {
  description = "Sampling ratio for Stackdriver logging (0.0 to 1.0)"
  type        = number
  default     = 1.0

  validation {
    condition     = var.logging_sampling_ratio >= 0.0 && var.logging_sampling_ratio <= 1.0
    error_message = "Logging sampling ratio must be between 0.0 and 1.0."
  }
}

variable "create_service_account" {
  description = "Whether to create a dedicated service account for Cloud Tasks"
  type        = bool
  default     = true
}

variable "service_account_id" {
  description = "Service account ID for Cloud Tasks invoker"
  type        = string
  default     = "cloudtasks-invoker"
}

variable "service_account_display_name" {
  description = "Display name for the Cloud Tasks service account"
  type        = string
  default     = "Cloud Tasks Invoker"
}

variable "grant_enqueuer_role" {
  description = "Grant cloudtasks.enqueuer role to the service account"
  type        = bool
  default     = true
}

variable "grant_run_invoker_role" {
  description = "Grant run.invoker role to the service account for OIDC"
  type        = bool
  default     = true
}

variable "grant_token_creator_role" {
  description = "Grant iam.serviceAccountTokenCreator role for OIDC token generation"
  type        = bool
  default     = false
}

variable "cloud_run_service_account_email" {
  description = "Cloud Run service account email to grant queue enqueuer permissions"
  type        = string
  default     = null
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
}

