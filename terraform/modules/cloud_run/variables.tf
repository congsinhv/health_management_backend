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

variable "service_account_email" {
  description = "Service account email to use for Cloud Run service"
  type        = string
}

# VPC Configuration
variable "use_direct_vpc_egress" {
  description = "Use Direct VPC Egress (preferred) instead of VPC Connector"
  type        = bool
  default     = true
}

variable "vpc_network_id" {
  description = "VPC network ID for Direct VPC Egress"
  type        = string
  default     = null
}

variable "vpc_subnet_id" {
  description = "VPC subnet ID for Direct VPC Egress"
  type        = string
  default     = null
}

variable "vpc_connector_id" {
  description = "VPC connector ID (fallback for Direct VPC Egress)"
  type        = string
  default     = null
}

variable "vpc_egress" {
  description = "VPC egress setting for VPC Connector"
  type        = string
  default     = "PRIVATE_RANGES_ONLY"
}

# Database Configuration
variable "cloud_sql_connection_name" {
  description = "Cloud SQL connection name"
  type        = string
  default     = null
}

variable "database_url" {
  description = "Database connection URL for services with direct DB access"
  type        = string
  default     = null
}

variable "redis_url" {
  description = "Redis connection URL"
  type        = string
  default     = null
}

# Resource Configuration
variable "cpu_limit" {
  description = "CPU limit"
  type        = string
}

variable "cpu_minimum" {
  description = "CPU minimum reservation"
  type        = string
  default     = null
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
  default     = 300
}

variable "concurrency" {
  description = "Maximum concurrent requests per instance"
  type        = number
  default     = 80
}

variable "session_affinity" {
  description = "Enable session affinity for stateful applications"
  type        = bool
  default     = false
}

# Container Configuration
variable "container_port" {
  description = "Container port"
  type        = number
  default     = 8080
}

variable "container_command" {
  description = "Container command to run"
  type        = list(string)
  default     = null
}

variable "container_args" {
  description = "Container arguments"
  type        = list(string)
  default     = null
}

variable "volume_mounts" {
  description = "Volume mounts for the container"
  type = map(object({
    name      = string
    mount_path = string
    read_only  = bool
  }))
  default = {}
}

variable "volumes" {
  description = "Volume definitions"
  type = map(object({
    name = string
    empty_dir = optional(object({
      medium = string
    }), null)
    secret = optional(object({
      name     = string
      optional = bool
      items = optional(map(object({
        key     = string
        path    = string
        mode    = string
        version = string
      })), {})
    }), null)
  }))
  default = {}
}

# Health Check Configuration
variable "health_check_path" {
  description = "Health check path"
  type        = string
  default     = "/health"
}

variable "ready_check_path" {
  description = "Readiness check path"
  type        = string
  default     = "/ready"
}

# Startup probe configuration
variable "startup_delay_seconds" {
  description = "Initial delay before startup probe"
  type        = number
  default     = 10
}

variable "startup_timeout_seconds" {
  description = "Startup probe timeout"
  type        = number
  default     = 3
}

variable "startup_period_seconds" {
  description = "Startup probe period"
  type        = number
  default     = 10
}

variable "startup_failure_threshold" {
  description = "Startup probe failure threshold"
  type        = number
  default     = 3
}

variable "startup_success_threshold" {
  description = "Startup probe success threshold"
  type        = number
  default     = 1
}

# Liveness probe configuration
variable "liveness_delay_seconds" {
  description = "Initial delay before liveness probe"
  type        = number
  default     = 30
}

variable "liveness_timeout_seconds" {
  description = "Liveness probe timeout"
  type        = number
  default     = 3
}

variable "liveness_period_seconds" {
  description = "Liveness probe period"
  type        = number
  default     = 30
}

variable "liveness_failure_threshold" {
  description = "Liveness probe failure threshold"
  type        = number
  default     = 3
}

variable "liveness_success_threshold" {
  description = "Liveness probe success threshold"
  type        = number
  default     = 1
}

# Readiness probe configuration
variable "enable_readiness_probe" {
  description = "Enable readiness probe"
  type        = bool
  default     = false
}

variable "readiness_delay_seconds" {
  description = "Initial delay before readiness probe"
  type        = number
  default     = 5
}

variable "readiness_timeout_seconds" {
  description = "Readiness probe timeout"
  type        = number
  default     = 3
}

variable "readiness_period_seconds" {
  description = "Readiness probe period"
  type        = number
  default     = 10
}

variable "readiness_failure_threshold" {
  description = "Readiness probe failure threshold"
  type        = number
  default     = 3
}

variable "readiness_success_threshold" {
  description = "Readiness probe success threshold"
  type        = number
  default     = 1
}

# Environment Variables
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

# Service URLs for Inter-Service Communication
variable "main_api_url" {
  description = "Main API service URL"
  type        = string
  default     = null
}

variable "chat_ai_url" {
  description = "Chat AI service URL"
  type        = string
  default     = null
}

variable "prediction_url" {
  description = "Prediction service URL"
  type        = string
  default     = null
}

# Traffic Configuration
variable "ingress" {
  description = "Ingress traffic setting"
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "traffic_type" {
  description = "Traffic type for the service"
  type        = string
  default     = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
}

variable "allow_public_access" {
  description = "Allow public unauthenticated access"
  type        = bool
  default     = true
}

# Resource Requests and Limits
variable "resource_limits" {
  description = "Resource limits for the container"
  type        = map(string)
  default     = null
}

variable "resource_requests" {
  description = "Resource requests for the container"
  type        = map(string)
  default     = null
}

# Metadata
variable "additional_labels" {
  description = "Additional labels to apply to the service"
  type        = map(string)
  default     = {}
}

variable "additional_annotations" {
  description = "Additional annotations to apply to the service"
  type        = map(string)
  default     = {}
}

variable "custom_domain" {
  description = "Custom domain name for the service"
  type        = string
  default     = null
}