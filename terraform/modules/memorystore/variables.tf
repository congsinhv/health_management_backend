variable "instance_name" {
  description = "Redis instance name"
  type        = string
}

variable "tier" {
  description = "Redis tier (BASIC or STANDARD_HA)"
  type        = string
  validation {
    condition     = contains(["BASIC", "STANDARD_HA"], var.tier)
    error_message = "Tier must be BASIC or STANDARD_HA"
  }
}

variable "memory_size_gb" {
  description = "Memory size in GB (1-300)"
  type        = number
  validation {
    condition     = var.memory_size_gb >= 1 && var.memory_size_gb <= 300
    error_message = "Memory size must be between 1 and 300 GB"
  }
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "redis_version" {
  description = "Redis version"
  type        = string
  default     = "REDIS_7_0"
}

variable "display_name" {
  description = "Display name for the instance"
  type        = string
}

variable "vpc_network" {
  description = "VPC network ID"
  type        = string
}

variable "environment" {
  description = "Environment (dev, prod)"
  type        = string
}

variable "maintenance_window_day" {
  description = "Maintenance window day (MONDAY-SUNDAY)"
  type        = string
  default     = "SUNDAY"
}

variable "maintenance_window_hour" {
  description = "Maintenance window start hour (0-23)"
  type        = number
  default     = 3
}