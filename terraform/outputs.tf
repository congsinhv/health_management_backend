output "artifact_registry_repository" {
  description = "Artifact Registry repository name"
  value       = module.artifact_registry.repository_name
}

output "artifact_registry_url" {
  description = "Artifact Registry repository URL"
  value       = module.artifact_registry.repository_url
}

output "cloud_run_service_account_email" {
  description = "Cloud Run service account email"
  value       = google_service_account.cloud_run_sa.email
}

output "vpc_connector_id" {
  description = "VPC connector ID"
  value       = module.vpc_connector.connector_id
}

output "vpc_connector_name" {
  description = "VPC connector name"
  value       = module.vpc_connector.connector_name
}

output "cloud_sql_instance_name" {
  description = "Cloud SQL instance name"
  value       = module.cloud_sql.instance_name
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name"
  value       = module.cloud_sql.connection_name
}

output "cloud_sql_database_name" {
  description = "Cloud SQL database name"
  value       = module.cloud_sql.database_name
}

output "cloud_sql_private_ip" {
  description = "Cloud SQL private IP address"
  value       = module.cloud_sql.private_ip_address
  sensitive   = true
}

output "cloud_run_service_name" {
  description = "Cloud Run service name"
  value       = module.cloud_run.service_name
}

output "cloud_run_service_url" {
  description = "Cloud Run service URL"
  value       = module.cloud_run.service_url
}

output "cloud_run_service_id" {
  description = "Cloud Run service ID"
  value       = module.cloud_run.service_id
}

output "secret_manager_secrets" {
  description = "Secret Manager secret names"
  value       = module.secret_manager.secret_names
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

output "project_id" {
  description = "GCP project ID"
  value       = var.project_id
}

output "region" {
  description = "GCP region"
  value       = var.region
}
