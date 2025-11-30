variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "services" {
  description = "Service configuration for alert policies"
  type = map(object({
    service_name = string
    error_rate_threshold = number
    latency_threshold_ms = number
  }))
}

variable "alert_enabled" {
  description = "Enable alert policies"
  type        = bool
  default     = true
}

variable "enable_cost_alerting" {
  description = "Enable cost alerting"
  type        = bool
  default     = false
}

variable "billing_account_id" {
  description = "Billing account ID for cost alerts"
  type        = string
  default     = null
}

variable "budget_threshold" {
  description = "Budget threshold for cost alerts"
  type        = number
  default     = 0.8  # 80%
}