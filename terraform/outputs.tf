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

output "cloud_sql_public_ip" {
  description = "Cloud SQL public IP address"
  value       = module.cloud_sql.public_ip_address
  sensitive   = true
}

output "cloud_run_service_name" {
  description = "Expected Cloud Run service name (for Jenkins deployment)"
  value       = var.cloud_run_service_name
}

output "cloud_run_config" {
  description = "Cloud Run configuration values for gcloud deployment"
  sensitive   = true
  value = {
    service_name          = var.cloud_run_service_name
    service_account_email = google_service_account.cloud_run_sa.email
    vpc_connector_id      = module.vpc_connector.connector_id
    sql_connection_name   = module.cloud_sql.connection_name
    secrets = {
      DATABASE_URL         = module.secret_manager.secret_versions["database_url"]
      DB_NAME              = module.secret_manager.secret_versions["db_name"]
      DB_USERNAME          = module.secret_manager.secret_versions["db_username"]
      DB_PASSWORD          = module.secret_manager.secret_versions["db_password"]
      DB_HOST              = module.secret_manager.secret_versions["db_host"]
      SECRET_KEY           = module.secret_manager.secret_versions["secret_key"]
      GOOGLE_CLIENT_ID     = module.secret_manager.secret_versions["google_client_id"]
      GOOGLE_CLIENT_SECRET = module.secret_manager.secret_versions["google_client_secret"]
      MAIL_USERNAME        = module.secret_manager.secret_versions["mail_username"]
      MAIL_PASSWORD        = module.secret_manager.secret_versions["mail_password"]
      MAIL_FROM            = module.secret_manager.secret_versions["mail_from"]
      MAIL_SERVER          = module.secret_manager.secret_versions["mail_server"]
      # Redis connection secrets
      REDIS_HOST         = var.enable_redis_cache ? module.secret_manager.secret_versions["redis_host"] : null
      REDIS_PORT         = var.enable_redis_cache ? module.secret_manager.secret_versions["redis_port"] : null
      REDIS_AUTH_SECRET  = var.enable_redis_cache ? module.secret_manager.secret_versions["redis_auth_secret"] : null
      ENABLE_REDIS_CACHE = var.enable_redis_cache ? module.secret_manager.secret_versions["enable_redis_cache"] : null
    }
  }
}

output "database_secret_names" {
  description = "Database credential secret names in Secret Manager"
  value = {
    db_name     = module.secret_manager.secret_names["db_name"]
    db_username = module.secret_manager.secret_names["db_username"]
    db_password = module.secret_manager.secret_names["db_password"]
    db_host     = module.secret_manager.secret_names["db_host"]
  }
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

# Cloud Scheduler Outputs
output "scheduler_job_name" {
  description = "Cloud Scheduler job name"
  value       = module.cloud_scheduler.job_name
}

output "scheduler_job_id" {
  description = "Cloud Scheduler job ID"
  value       = module.cloud_scheduler.job_id
}

output "scheduler_schedule" {
  description = "Cloud Scheduler cron schedule"
  value       = module.cloud_scheduler.schedule
}

output "scheduler_target_uri" {
  description = "Cloud Scheduler HTTP target URI"
  value       = module.cloud_scheduler.http_target_uri
}

output "scheduler_state" {
  description = "Cloud Scheduler job state"
  value       = module.cloud_scheduler.state
}

output "scheduler_service_account_email" {
  description = "Cloud Scheduler service account email"
  value       = google_service_account.cloud_scheduler_sa.email
}

# Redis/Memorystore Outputs
output "redis_host" {
  description = "Redis instance host"
  value       = var.enable_redis_cache ? module.memorystore.redis_host : null
}

output "redis_port" {
  description = "Redis instance port"
  value       = var.enable_redis_cache ? module.memorystore.redis_port : null
}

output "redis_url" {
  description = "Redis connection URL"
  value       = var.enable_redis_cache ? module.memorystore.redis_url : null
  sensitive   = true
}

output "redis_auth_secret" {
  description = "Secret Manager secret for Redis auth"
  value       = var.enable_redis_cache ? module.memorystore.redis_auth_secret : null
}

output "redis_instance_id" {
  description = "Redis instance ID"
  value       = var.enable_redis_cache ? module.memorystore.redis_instance_id : null
}

output "redis_memory_size_gb" {
  description = "Redis memory size in GB"
  value       = var.enable_redis_cache ? module.memorystore.redis_memory_size_gb : null
}

output "redis_tier" {
  description = "Redis tier"
  value       = var.enable_redis_cache ? module.memorystore.redis_tier : null
}
