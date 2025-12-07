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
  description = "Environment name (test, prod)"
  type        = string
  validation {
    condition     = contains(["test", "prod"], var.environment)
    error_message = "Environment must be either 'test' or 'prod'."
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
  description = "Base custom domain (e.g., vhealth.io.vn)"
  type        = string
  default     = ""
}

variable "api_subdomain" {
  description = "API subdomain (e.g., 'api' for api.vhealth.io.vn or 'dev.api' for dev.api.vhealth.io.vn)"
  type        = string
  default     = "api"
}

variable "enable_cdn" {
  description = "Enable Cloud CDN for the API load balancer"
  type        = bool
  default     = true
}

# Cloud Scheduler Variables
variable "scheduler_endpoint_url" {
  description = "Full URL endpoint that Cloud Scheduler will invoke (e.g., https://your-service.run.app/api/v1/scheduler/hello-world)"
  type        = string
}

variable "scheduler_cron_schedule" {
  description = "Cron expression for the scheduler (e.g., '*/30 * * * *' for every 30 minutes)"
  type        = string
  default     = "*/30 * * * *"
}

variable "scheduler_time_zone" {
  description = "Time zone for the scheduler (e.g., 'UTC', 'America/New_York')"
  type        = string
  default     = "UTC"
}

variable "scheduler_use_oidc_auth" {
  description = "Whether to use OIDC authentication for Cloud Scheduler (set to true if Cloud Run requires authentication)"
  type        = bool
  default     = false
}

variable "scheduler_paused" {
  description = "Whether the scheduler job should be paused"
  type        = bool
  default     = false
}

# Redis/Memorystore Variables
variable "redis_tier" {
  description = "Redis tier (BASIC for dev, STANDARD_HA for prod)"
  type        = string
  default     = "BASIC"
}

variable "redis_memory_size_gb" {
  description = "Redis memory size in GB"
  type        = number
  default     = 1
}

variable "redis_version" {
  description = "Redis version"
  type        = string
  default     = "REDIS_7_0"
}

variable "redis_maintenance_day" {
  description = "Maintenance window day"
  type        = string
  default     = "SUNDAY"
}

variable "redis_maintenance_hour" {
  description = "Maintenance window start hour (0-23)"
  type        = number
  default     = 3
}

variable "enable_redis_cache" {
  description = "Enable Redis caching"
  type        = bool
  default     = true
}

# ============================================================================
# Cloud Tasks Variables - Notification Queue
# ============================================================================
variable "enable_cloud_tasks" {
  description = "Enable Cloud Tasks queue for notifications"
  type        = bool
  default     = true
}

variable "cloud_tasks_queue_name" {
  description = "Name of the Cloud Tasks queue for notifications"
  type        = string
  default     = "workout-notifications"
}

variable "cloud_tasks_max_dispatches_per_second" {
  description = "Maximum tasks dispatched per second"
  type        = number
  default     = 500
}

variable "cloud_tasks_max_burst_size" {
  description = "Maximum tasks dispatched in a single burst"
  type        = number
  default     = 100
}

variable "cloud_tasks_max_concurrent_dispatches" {
  description = "Maximum concurrent task executions"
  type        = number
  default     = 1000
}

variable "cloud_tasks_max_attempts" {
  description = "Maximum retry attempts for failed tasks"
  type        = number
  default     = 3
}

variable "cloud_tasks_min_backoff" {
  description = "Minimum backoff duration between retries"
  type        = string
  default     = "1s"
}

variable "cloud_tasks_max_backoff" {
  description = "Maximum backoff duration between retries"
  type        = string
  default     = "3600s"
}

variable "cloud_tasks_max_doublings" {
  description = "Maximum number of times the backoff duration is doubled"
  type        = number
  default     = 16
}

variable "cloud_tasks_enable_logging" {
  description = "Enable Stackdriver logging for Cloud Tasks"
  type        = bool
  default     = true
}

variable "cloud_tasks_logging_sampling_ratio" {
  description = "Sampling ratio for Cloud Tasks logging (0.0 to 1.0)"
  type        = number
  default     = 1.0
}

# ============================================================================
# Notification Scheduler Variables
# ============================================================================
variable "enable_notification_scheduler" {
  description = "Enable Cloud Scheduler for notification batch processing"
  type        = bool
  default     = true
}

variable "notification_scheduler_interval_minutes" {
  description = "Interval in minutes for notification batch processing (default: 5)"
  type        = number
  default     = 5
}

variable "notification_scheduler_paused" {
  description = "Whether the notification scheduler should be paused"
  type        = bool
  default     = false
}

variable "backend_url" {
  description = "Backend URL for Cloud Scheduler to invoke (e.g., https://api.vhealth.io.vn)"
  type        = string
}
