variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "secrets" {
  description = "Map of secret names to secret values"
  type        = map(string)
}

variable "service_account_email" {
  description = "Service account email to grant secret access"
  type        = string
}
