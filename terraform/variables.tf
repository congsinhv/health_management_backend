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

# Microservices Architecture Variables
variable "title_case_environment" {
  description = "Environment name in title case"
  type        = string
  default     = "Development"
}

# VPC Network Configuration (Direct VPC Egress)
variable "subnet_cidr" {
  description = "CIDR range for the subnet"
  type        = string
}

variable "use_vpc_connector_fallback" {
  description = "Whether to use VPC Connector as fallback"
  type        = bool
  default     = false
}

variable "enable_private_service_connect" {
  description = "Enable Private Service Connect for Cloud SQL"
  type        = bool
  default     = false
}

# Service Account Configuration
variable "openai_secret_id" {
  description = "Secret Manager secret ID for OpenAI API key"
  type        = string
}

variable "app_secrets_id" {
  description = "Secret Manager secret ID for application secrets"
  type        = string
}

variable "google_client_secret_id" {
  description = "Secret Manager secret ID for Google client secrets"
  type        = string
}

# Main API Service Configuration
variable "main_api_image" {
  description = "Container image for Main API service"
  type        = string
}

variable "main_api_cpu" {
  description = "CPU limit for Main API service"
  type        = string
}

variable "main_api_cpu_minimum" {
  description = "CPU minimum reservation for Main API service"
  type        = string
  default     = null
}

variable "main_api_memory" {
  description = "Memory limit for Main API service"
  type        = string
}

variable "main_api_min_instances" {
  description = "Minimum instances for Main API service"
  type        = number
}

variable "main_api_max_instances" {
  description = "Maximum instances for Main API service"
  type        = number
}

variable "main_api_timeout" {
  description = "Request timeout for Main API service (seconds)"
  type        = number
}

variable "main_api_concurrency" {
  description = "Maximum concurrent requests for Main API"
  type        = number
}

variable "main_api_startup_delay" {
  description = "Startup probe delay for Main API service"
  type        = number
  default     = 10
}

variable "main_api_liveness_delay" {
  description = "Liveness probe delay for Main API service"
  type        = number
  default     = 30
}

variable "main_api_ingress" {
  description = "Ingress traffic setting for Main API"
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "main_api_custom_domain" {
  description = "Custom domain for Main API service"
  type        = string
  default     = null
}

# Chat AI Service Configuration
variable "chat_ai_image" {
  description = "Container image for Chat AI service"
  type        = string
}

variable "chat_ai_cpu" {
  description = "CPU limit for Chat AI service"
  type        = string
}

variable "chat_ai_cpu_minimum" {
  description = "CPU minimum reservation for Chat AI service"
  type        = string
  default     = null
}

variable "chat_ai_memory" {
  description = "Memory limit for Chat AI service"
  type        = string
}

variable "chat_ai_min_instances" {
  description = "Minimum instances for Chat AI service"
  type        = number
}

variable "chat_ai_max_instances" {
  description = "Maximum instances for Chat AI service"
  type        = number
}

variable "chat_ai_timeout" {
  description = "Request timeout for Chat AI service (seconds)"
  type        = number
}

variable "chat_ai_concurrency" {
  description = "Maximum concurrent requests for Chat AI"
  type        = number
}

variable "chat_ai_startup_delay" {
  description = "Startup probe delay for Chat AI service"
  type        = number
  default     = 15
}

variable "chat_ai_liveness_delay" {
  description = "Liveness probe delay for Chat AI service"
  type        = number
  default     = 45
}

variable "chat_ai_ingress" {
  description = "Ingress traffic setting for Chat AI"
  type        = string
  default     = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
}

# Prediction Service Configuration
variable "prediction_image" {
  description = "Container image for Prediction service"
  type        = string
}

variable "prediction_cpu" {
  description = "CPU limit for Prediction service"
  type        = string
}

variable "prediction_cpu_minimum" {
  description = "CPU minimum reservation for Prediction service"
  type        = string
  default     = null
}

variable "prediction_memory" {
  description = "Memory limit for Prediction service"
  type        = string
}

variable "prediction_min_instances" {
  description = "Minimum instances for Prediction service"
  type        = number
}

variable "prediction_max_instances" {
  description = "Maximum instances for Prediction service"
  type        = number
}

variable "prediction_timeout" {
  description = "Request timeout for Prediction service (seconds)"
  type        = number
}

variable "prediction_concurrency" {
  description = "Maximum concurrent requests for Prediction"
  type        = number
}

variable "prediction_startup_delay" {
  description = "Startup probe delay for Prediction service"
  type        = number
  default     = 10
}

variable "prediction_liveness_delay" {
  description = "Liveness probe delay for Prediction service"
  type        = number
  default     = 30
}

variable "prediction_ingress" {
  description = "Ingress traffic setting for Prediction"
  type        = string
  default     = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
}

# Model and Storage Configuration
variable "gcp_model_bucket" {
  description = "GCS bucket for model storage"
  type        = string
}

variable "qa_model_path" {
  description = "Path to QA model in GCS"
  type        = string
}

variable "prediction_model_path" {
  description = "Path to prediction model in GCS"
  type        = string
}

# Database Configuration
variable "database_url" {
  description = "Database connection URL"
  type        = string
  default     = null
}

variable "redis_url" {
  description = "Redis connection URL"
  type        = string
  default     = null
}

# Existing Resources Integration
variable "use_existing_cloud_sql" {
  description = "Use existing Cloud SQL instance"
  type        = bool
  default     = true
}

variable "redis_instance_name" {
  description = "Name of existing Redis instance"
  type        = string
  default     = null
}

variable "use_existing_redis" {
  description = "Use existing Redis instance"
  type        = bool
  default     = true
}

# Service Communication
variable "enable_reverse_communication" {
  description = "Enable AI services to call back to Main API"
  type        = bool
  default     = false
}

variable "enable_debug_access" {
  description = "Enable debug access for services"
  type        = bool
  default     = false
}

variable "enable_time_restrictions" {
  description = "Enable time-based access restrictions"
  type        = bool
  default     = false
}

# Database Access for AI Services
variable "enable_chat_ai_db_access" {
  description = "Enable direct database access for Chat AI service"
  type        = bool
  default     = false
}

variable "enable_prediction_db_access" {
  description = "Enable direct database access for Prediction service"
  type        = bool
  default     = false
}

# Application Configuration
variable "debug_enabled" {
  description = "Enable debug mode"
  type        = bool
  default     = false
}

variable "health_check_path" {
  description = "Health check path for services"
  type        = string
  default     = "/health"
}

# Monitoring and Alerting
variable "enable_monitoring" {
  description = "Enable monitoring dashboard"
  type        = bool
  default     = false
}

variable "enable_alerting" {
  description = "Enable alert policies"
  type        = bool
  default     = false
}

variable "notification_channel_id" {
  description = "Notification channel ID for alerts"
  type        = string
  default     = null
}

# Main API Environment Variables
variable "main_api_env_vars" {
  description = "Additional environment variables for Main API"
  type        = map(string)
  default     = {}
}

# Chat AI Environment Variables
variable "chat_ai_env_vars" {
  description = "Additional environment variables for Chat AI"
  type        = map(string)
  default     = {}
}

# Prediction Environment Variables
variable "prediction_env_vars" {
  description = "Additional environment variables for Prediction"
  type        = map(string)
  default     = {}
}

