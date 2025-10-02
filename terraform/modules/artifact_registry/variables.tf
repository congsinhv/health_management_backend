variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "repository_id" {
  description = "Artifact Registry repository ID"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "service_account_email" {
  description = "Service account email to grant access to the repository"
  type        = string
}
