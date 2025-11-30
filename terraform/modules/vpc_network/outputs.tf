output "network_id" {
  description = "VPC network ID for Direct VPC Egress"
  value       = google_compute_network.vpc_network.id
}

output "network_self_link" {
  description = "VPC network self-link"
  value       = google_compute_network.vpc_network.self_link
}

output "subnet_id" {
  description = "Subnet ID for Cloud Run services"
  value       = google_compute_subnetwork.subnet.id
}

output "subnet_self_link" {
  description = "Subnet self-link for Direct VPC Egress configuration"
  value       = google_compute_subnetwork.subnet.self_link
}

output "subnet_name" {
  description = "Subnet name"
  value       = google_compute_subnetwork.subnet.name
}

output "connector_id" {
  description = "VPC Connector ID (backward compatibility)"
  value       = var.use_vpc_connector ? google_vpc_access_connector.connector[0].id : null
}

output "connector_name" {
  description = "VPC Connector name"
  value       = var.use_vpc_connector ? google_vpc_access_connector.connector[0].name : null
}

output "psc_endpoint_ip" {
  description = "Private Service Connect endpoint IP for Cloud SQL"
  value       = var.enable_private_service_connect ? google_compute_global_address.psc_endpoint[0].address : null
}