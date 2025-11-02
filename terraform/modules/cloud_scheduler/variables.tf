variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Scheduler"
  type        = string
}

variable "job_name" {
  description = "Name of the Cloud Scheduler job"
  type        = string
}

variable "description" {
  description = "Description of the scheduler job"
  type        = string
  default     = "Scheduled job created by Terraform"
}

variable "schedule" {
  description = "Cron expression for the schedule (e.g., '*/30 * * * *' for every 30 minutes)"
  type        = string
}

variable "time_zone" {
  description = "Time zone for the schedule (e.g., 'America/New_York')"
  type        = string
  default     = "UTC"
}

variable "http_target_uri" {
  description = "HTTP URI to invoke"
  type        = string
}

variable "http_method" {
  description = "HTTP method to use (GET, POST, PUT, DELETE, PATCH)"
  type        = string
  default     = "POST"
}

variable "http_body" {
  description = "HTTP request body (base64 encoded)"
  type        = string
  default     = null
}

variable "http_headers" {
  description = "HTTP headers to include in the request"
  type        = map(string)
  default     = {}
}

variable "attempt_deadline" {
  description = "The deadline for job attempts (e.g., '320s')"
  type        = string
  default     = "320s"
}

variable "retry_config" {
  description = "Retry configuration for failed jobs"
  type = object({
    retry_count          = optional(number, 3)
    max_retry_duration   = optional(string, "0s")
    min_backoff_duration = optional(string, "5s")
    max_backoff_duration = optional(string, "3600s")
    max_doublings        = optional(number, 16)
  })
  default = {
    retry_count          = 3
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "3600s"
    max_doublings        = 16
  }
}

variable "service_account_email" {
  description = "Service account email for authentication (optional, for authenticated endpoints)"
  type        = string
  default     = null
}

variable "oidc_token" {
  description = "Whether to use OIDC token for authentication"
  type        = bool
  default     = false
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
}

variable "paused" {
  description = "Whether the job should be paused"
  type        = bool
  default     = false
}

