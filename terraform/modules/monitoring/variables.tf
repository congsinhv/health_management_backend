variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "services" {
  description = "Service configuration for monitoring dashboard"
  type = map(object({
    service_name = string
    display_name = string
  }))
}

variable "dashboard_name" {
  description = "Dashboard name"
  type        = string
  default     = null
}

variable "dashboard_display_name" {
  description = "Dashboard display name"
  type        = string
  default     = null
}