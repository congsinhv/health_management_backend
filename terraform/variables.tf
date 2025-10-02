variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be either 'dev' or 'prod'."
  }
}

# Artifact Registry Variables
variable "artifact_registry_repository_id" {
  description = "Artifact Registry repository ID"
  type        = string
}

# VPC Connector Variables
variable "vpc_connector_name" {
  description = "VPC connector name"
  type        = string
}

variable "vpc_network" {
  description = "VPC network name"
  type        = string
  default     = "default"
}

variable "vpc_connector_ip_range" {
  description = "IP CIDR range for VPC connector"
  type        = string
}

variable "vpc_connector_min_instances" {
  description = "Minimum number of VPC connector instances"
  type        = number
  default     = 2
}

variable "vpc_connector_max_instances" {
  description = "Maximum number of VPC connector instances"
  type        = number
  default     = 3
}

variable "vpc_connector_machine_type" {
  description = "Machine type for VPC connector"
  type        = string
  default     = "e2-micro"
}

# Cloud SQL Variables
variable "cloud_sql_instance_name" {
  description = "Cloud SQL instance name"
  type        = string
}

variable "cloud_sql_database_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "POSTGRES_15"
}

variable "cloud_sql_tier" {
  description = "Cloud SQL machine tier"
  type        = string
}

variable "cloud_sql_availability_type" {
  description = "Cloud SQL availability type (ZONAL or REGIONAL)"
  type        = string
  default     = "ZONAL"
}

variable "cloud_sql_backup_enabled" {
  description = "Enable automated backups"
  type        = bool
  default     = true
}

variable "cloud_sql_backup_start_time" {
  description = "Start time for automated backups (HH:MM format)"
  type        = string
  default     = "03:00"
}

variable "cloud_sql_database_name" {
  description = "Database name"
  type        = string
  default     = "health_management"
}

variable "cloud_sql_deletion_protection" {
  description = "Enable deletion protection for Cloud SQL"
  type        = bool
}

# Cloud Run Variables
variable "cloud_run_service_name" {
  description = "Cloud Run service name"
  type        = string
}

variable "cloud_run_image" {
  description = "Container image for Cloud Run"
  type        = string
}

variable "cloud_run_cpu_limit" {
  description = "CPU limit for Cloud Run"
  type        = string
  default     = "1000m"
}

variable "cloud_run_memory_limit" {
  description = "Memory limit for Cloud Run"
  type        = string
  default     = "512Mi"
}

variable "cloud_run_max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = number
}

variable "cloud_run_min_instances" {
  description = "Minimum number of Cloud Run instances"
  type        = number
  default     = 0
}

variable "cloud_run_timeout_seconds" {
  description = "Request timeout in seconds"
  type        = number
  default     = 300
}

variable "cloud_run_concurrency" {
  description = "Maximum concurrent requests per instance"
  type        = number
  default     = 80
}

# Secret Manager Variables

variable "secret_key" {
  description = "JWT secret key (will be stored in Secret Manager)"
  type        = string
  sensitive   = true
}

variable "google_client_id" {
  description = "Google OAuth client ID (will be stored in Secret Manager)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "google_client_secret" {
  description = "Google OAuth client secret (will be stored in Secret Manager)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "mail_username" {
  description = "Email username (will be stored in Secret Manager)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "mail_password" {
  description = "Email password (will be stored in Secret Manager)"
  type        = string
  sensitive   = true
  default     = ""
}

# Application Environment Variables
variable "debug" {
  description = "Enable debug mode"
  type        = string
  default     = "false"
}

variable "log_level" {
  description = "Logging level"
  type        = string
  default     = "INFO"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "Health Management API"
}

variable "app_version" {
  description = "Application version"
  type        = string
  default     = "1.0.0"
}

variable "mail_server" {
  description = "SMTP server address"
  type        = string
  default     = "smtp.gmail.com"
}

variable "mail_port" {
  description = "SMTP server port"
  type        = string
  default     = "587"
}

variable "mail_from" {
  description = "From email address"
  type        = string
  default     = ""
}

variable "webui_url" {
  description = "Web UI URL"
  type        = string
  default     = ""
}

# Domain Configuration (Optional)
variable "enable_custom_domain" {
  description = "Enable custom domain mapping for Cloud Run"
  type        = bool
  default     = false
}

variable "custom_domain" {
  description = "Base custom domain (e.g., vhealth.io.net)"
  type        = string
  default     = ""
}

variable "api_subdomain" {
  description = "API subdomain (e.g., 'api' for api.vhealth.io.net or 'dev.api' for dev.api.vhealth.io.net)"
  type        = string
  default     = "api"
}

variable "enable_cdn" {
  description = "Enable Cloud CDN for the API load balancer"
  type        = bool
  default     = true
}
