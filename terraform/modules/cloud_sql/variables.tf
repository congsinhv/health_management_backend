variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "instance_name" {
  description = "Cloud SQL instance name"
  type        = string
}

variable "database_version" {
  description = "PostgreSQL version"
  type        = string
}

variable "tier" {
  description = "Cloud SQL tier"
  type        = string
}

variable "availability_type" {
  description = "Availability type (ZONAL or REGIONAL)"
  type        = string
}

variable "backup_enabled" {
  description = "Enable backups"
  type        = bool
}

variable "backup_start_time" {
  description = "Backup start time (HH:MM format)"
  type        = string
}

variable "database_name" {
  description = "Database name"
  type        = string
}

variable "deletion_protection" {
  description = "Enable deletion protection"
  type        = bool
}

variable "environment" {
  description = "Environment name"
  type        = string
}
