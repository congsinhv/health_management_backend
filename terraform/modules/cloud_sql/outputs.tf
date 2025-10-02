output "instance_name" {
  description = "Cloud SQL instance name"
  value       = google_sql_database_instance.instance.name
}

output "connection_name" {
  description = "Cloud SQL connection name"
  value       = google_sql_database_instance.instance.connection_name
}

output "database_name" {
  description = "Database name"
  value       = google_sql_database.database.name
}

output "public_ip_address" {
  description = "Public IP address"
  value       = google_sql_database_instance.instance.public_ip_address
  sensitive   = true
}

output "db_user" {
  description = "Database user"
  value       = google_sql_user.user.name
}

output "db_password" {
  description = "Database password"
  value       = random_password.db_password.result
  sensitive   = true
}
