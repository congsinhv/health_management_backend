variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "asia-southeast1"
}

variable "subnet_cidr" {
  description = "CIDR range for the subnet"
  type        = string
  default     = "10.8.0.0/28"
}

variable "use_vpc_connector" {
  description = "Whether to create VPC Connector for backward compatibility"
  type        = bool
  default     = false
}

variable "connector_cidr" {
  description = "CIDR range for VPC Connector"
  type        = string
  default     = "10.8.0.0/28"
}

variable "connector_min_instances" {
  description = "Minimum instances for VPC Connector"
  type        = number
  default     = 2
}

variable "connector_max_instances" {
  description = "Maximum instances for VPC Connector"
  type        = number
  default     = 3
}

variable "enable_private_service_connect" {
  description = "Enable Private Service Connect for Cloud SQL"
  type        = bool
  default     = false
}

variable "private_service_connect_ip" {
  description = "Static IP for Private Service Connect endpoint"
  type        = string
  default     = "10.8.0.10"
}