variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "service_name" {
  description = "Cloud Run service name"
  type        = string
}

variable "image" {
  description = "Container image"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_connector_id" {
  description = "VPC connector ID"
  type        = string
}

variable "cloud_sql_connection_name" {
  description = "Cloud SQL connection name"
  type        = string
}

variable "cpu_limit" {
  description = "CPU limit"
  type        = string
}

variable "memory_limit" {
  description = "Memory limit"
  type        = string
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
}

variable "timeout_seconds" {
  description = "Request timeout in seconds"
  type        = number
}

variable "concurrency" {
  description = "Maximum concurrent requests per instance"
  type        = number
}

variable "secret_env_vars" {
  description = "Map of environment variable names to secret version IDs"
  type        = map(string)
  default     = {}
}

variable "env_vars" {
  description = "Map of environment variable names to values"
  type        = map(string)
  default     = {}
}

variable "service_account_email" {
  description = "Service account email to use for Cloud Run service"
  type        = string
}
