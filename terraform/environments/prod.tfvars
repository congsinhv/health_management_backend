# Project Configuration
project_id  = "vhealth-prod"
region      = "asia-southeast1" # Singapore - closest to Vietnam (~1000km, ~10-20ms latency)
environment = "prod"

# Artifact Registry
artifact_registry_repository_id = "vhealth-backend-prod"

# VPC Connector
vpc_connector_name          = "vhealth-vpc-conn-prod"
vpc_network                 = "default"
vpc_connector_ip_range      = "10.9.0.0/28"
vpc_connector_min_instances = 2
vpc_connector_max_instances = 10
vpc_connector_machine_type  = "e2-standard-4"

# Cloud SQL (now uses public IP with restricted authorized networks recommended)
cloud_sql_instance_name       = "vhealth-backend-db-prod"
cloud_sql_database_version    = "POSTGRES_15"
cloud_sql_tier                = "db-custom-2-7680"
cloud_sql_availability_type   = "REGIONAL" # Multi-zone in asia-southeast1 for high availability
cloud_sql_backup_enabled      = true
cloud_sql_backup_start_time   = "20:00" # 3 AM Vietnam time (UTC+7)
cloud_sql_database_name       = "health_management"
cloud_sql_deletion_protection = true
# Note: cloud_sql_private_ip_name removed - using public IP now
# IMPORTANT: For production, restrict authorized_networks in modules/cloud_sql/main.tf

# Cloud Run
cloud_run_service_name    = "vhealth-backend-prod"
cloud_run_image           = "asia-southeast1-docker.pkg.dev/vhealth-prod/vhealth-backend-prod/health-api:latest"
cloud_run_cpu_limit       = "2000m"
cloud_run_memory_limit    = "1Gi"
cloud_run_max_instances   = 100
cloud_run_min_instances   = 1
cloud_run_timeout_seconds = 300
cloud_run_concurrency     = 80

# Secret Manager (These should be provided via environment variables or secure injection)
# database_url         = "postgresql://user:password@host:5432/dbname"
# secret_key          = "your-jwt-secret-key"
# google_client_id    = "your-google-oauth-client-id"
# google_client_secret = "your-google-oauth-client-secret"
# mail_username       = "your-email@gmail.com"
# mail_password       = "your-email-password"

# Application Settings
debug       = "false"
log_level   = "INFO"
app_name    = "Health Management API"
app_version = "1.0.0"
mail_server = "smtp.gmail.com"
mail_port   = "587"
mail_from   = "noreply@healthmanagement.com"
webui_url   = "https://healthmanagement.com"

# Domain Configuration (Optional - set enable_custom_domain = true to activate)
enable_custom_domain = true  # Set to true when ready to configure custom domain
custom_domain        = "vhealth.io.net"
api_subdomain        = "api"  # This will create api.vhealth.io.net
enable_cdn           = true
