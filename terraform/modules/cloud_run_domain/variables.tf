variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region for regional resources"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., dev, prod)"
  type        = string
}

variable "cloud_run_service_name" {
  description = "Name of the Cloud Run service to map the domain to"
  type        = string
}

variable "domain_name" {
  description = "Full domain name to map to the Cloud Run service (e.g., api.vhealth.io.net)"
  type        = string
}

variable "enable_cdn" {
  description = "Enable Cloud CDN for the backend service"
  type        = bool
  default     = true
}
