# Project Configuration
project_id  = "vhealth-test"
region      = "asia-southeast1"
environment = "test"

# Artifact Registry
artifact_registry_repository_id = "vhealth-backend-test"

# VPC Connector (needed for Redis)
vpc_connector_name          = "vhealth-vpc-conn-test"
vpc_network                 = "default"
vpc_connector_ip_range      = "10.9.0.0/28"  # Different from prod
vpc_connector_min_instances = 2
vpc_connector_max_instances = 3
vpc_connector_machine_type  = "e2-micro"

# Cloud SQL (Minimal tier)
cloud_sql_instance_name       = "vhealth-backend-db-test"
cloud_sql_database_version    = "POSTGRES_15"
cloud_sql_tier                = "db-f1-micro"  # Smallest instance
cloud_sql_availability_type   = "ZONAL"
cloud_sql_backup_enabled      = true
cloud_sql_backup_start_time   = "20:00"
cloud_sql_database_name       = "health_management"
cloud_sql_deletion_protection = false  # Allow deletion in test

# Cloud Run (Minimal resources)
cloud_run_service_name    = "vhealth-backend-test"
cloud_run_image           = "asia-southeast1-docker.pkg.dev/vhealth-test/vhealth-backend-test/health-api:latest"
cloud_run_cpu_limit       = "2000m"  # Need 2 vCPU for model loading
cloud_run_memory_limit    = "2Gi"    # Need 2GB for SBERT model
cloud_run_max_instances   = 3        # Low max for cost control
cloud_run_min_instances   = 0        # Scale to zero when idle
cloud_run_timeout_seconds = 300
cloud_run_concurrency     = 15

# Application Settings
debug       = "true"
log_level   = "DEBUG"
app_name    = "Health Management API - Test"
app_version = "1.0.0-test"
mail_server = "smtp.gmail.com"
mail_port   = "587"
mail_from   = "congsynh.vo@gmail.com"
webui_url   = "https://test.vhealth.io.vn"

# Domain Configuration - DISABLED (will configure later)
enable_custom_domain = false
custom_domain        = "vhealth.io.vn"
api_subdomain        = "test.api"
enable_cdn           = false

# Cloud Scheduler - DISABLED (commented out in main.tf)
scheduler_endpoint_url    = "PLACEHOLDER_URL"
scheduler_cron_schedule   = "*/30 * * * *"
scheduler_time_zone       = "Asia/Ho_Chi_Minh"
scheduler_use_oidc_auth   = false
scheduler_paused          = true

# Redis Configuration - ENABLED
redis_tier           = "BASIC"  # No HA for test
redis_memory_size_gb = 1        # Minimum size
enable_redis_cache   = true
