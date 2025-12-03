# Project Configuration
project_id  = "vhealth-prod"
region      = "asia-southeast1"
environment = "prod"

# Artifact Registry
artifact_registry_repository_id = "vhealth-backend-prod"

# VPC Connector
vpc_connector_name          = "vhealth-vpc-conn-prod"
vpc_network                 = "default"
vpc_connector_ip_range      = "10.10.0.0/28"
vpc_connector_min_instances = 2
vpc_connector_max_instances = 3
vpc_connector_machine_type  = "e2-micro"

# Cloud SQL
cloud_sql_instance_name       = "vhealth-backend-db-prod"
cloud_sql_database_version    = "POSTGRES_15"
cloud_sql_tier                = "db-f1-micro"
cloud_sql_availability_type   = "ZONAL"
cloud_sql_backup_enabled      = true
cloud_sql_backup_start_time   = "20:00"
cloud_sql_database_name       = "health_management"
cloud_sql_deletion_protection = true

# Cloud Run (Phase 4 Optimized - Dec 2025)
cloud_run_service_name    = "vhealth-backend-prod"
cloud_run_image           = "asia-southeast1-docker.pkg.dev/vhealth-prod/vhealth-backend-prod/health-api:latest"
cloud_run_cpu_limit       = "2000m"
cloud_run_memory_limit    = "1.5Gi"   # Reduced from 4Gi (Phase 1 ONNX quantization enables 1Gi)
cloud_run_max_instances   = 10
cloud_run_min_instances   = 1       # Changed from 0 (Phase 2 lazy loading eliminates cold-start cost)
cloud_run_timeout_seconds = 300
cloud_run_concurrency     = 20      # Reduced from 80 (safe limit for 1Gi memory)

# Application Settings
debug       = "false"
log_level   = "INFO"
app_name    = "Health Management API"
app_version = "1.0.0"
mail_server = "smtp.gmail.com"
mail_port   = "587"
mail_from   = "congsynh.vo@gmail.com"
webui_url   = "https://vhealth.io.vn"

# Domain Configuration
enable_custom_domain = true
custom_domain        = "vhealth.io.vn"
api_subdomain        = "api"
enable_cdn           = true

# Cloud Scheduler Configuration
scheduler_endpoint_url  = "https://api.vhealth.io.vn/api/v1/scheduler/hello-world"
scheduler_cron_schedule = "*/30 * * * *"
scheduler_time_zone     = "Asia/Ho_Chi_Minh"
scheduler_use_oidc_auth = false
scheduler_paused        = false

# Redis Configuration
redis_tier           = "BASIC"
redis_memory_size_gb = 1
enable_redis_cache   = true
