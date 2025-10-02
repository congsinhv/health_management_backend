variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
}

variable "connector_name" {
  description = "VPC connector name"
  type        = string
}

variable "vpc_network" {
  description = "VPC network name"
  type        = string
}

variable "ip_cidr_range" {
  description = "IP CIDR range for VPC connector"
  type        = string
}

variable "min_instances" {
  description = "Minimum number of instances"
  type        = number
}

variable "max_instances" {
  description = "Maximum number of instances"
  type        = number
}

variable "machine_type" {
  description = "Machine type"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}
