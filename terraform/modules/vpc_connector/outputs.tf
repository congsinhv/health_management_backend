output "connector_id" {
  description = "VPC connector ID"
  value       = google_vpc_access_connector.connector.id
}

output "connector_name" {
  description = "VPC connector name"
  value       = google_vpc_access_connector.connector.name
}

output "connector_self_link" {
  description = "VPC connector self link"
  value       = google_vpc_access_connector.connector.self_link
}
