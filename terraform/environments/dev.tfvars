# VHealth Development Environment Configuration - Microservices Architecture
# Project Configuration
project_id     = "vhealth-dev"
region          = "asia-southeast1"
environment      = "dev"
title_case_environment = "Development"

# VPC Network Configuration (Direct VPC Egress)
subnet_cidr = "10.8.0.0/28"
use_vpc_connector_fallback = true  # Keep VPC Connector for dev stability
vpc_connector_cidr = "10.8.0.0/28"
vpc_connector_min_instances = 2
vpc_connector_max_instances = 3
enable_private_service_connect = false

# Existing Resources Integration
use_existing_cloud_sql = true
cloud_sql_instance_name = "vhealth-backend-db-dev"
use_existing_redis = true
redis_instance_name = "vhealth-cache-dev"

# Secret Manager Configuration
openai_secret_id = "vhealth-dev-openai-api-key"
app_secrets_id = "vhealth-dev-app-secrets"
google_client_secret_id = "vhealth-dev-google-client-secret"

# Main API Service Configuration
main_api_image = "asia-southeast1-docker.pkg.dev/vhealth-dev/vhealth-backend-dev/main-api:latest"
main_api_cpu = "2000m"
main_api_cpu_minimum = "1000m"
main_api_memory = "2048Mi"
main_api_min_instances = 0  # Cost optimization for dev
main_api_max_instances = 3
main_api_timeout = 300
main_api_concurrency = 15
main_api_startup_delay = 10
main_api_liveness_delay = 30
main_api_ingress = "INGRESS_TRAFFIC_ALL"
main_api_custom_domain = "dev.api.vhealth.io.vn"

# Chat AI Service Configuration
chat_ai_image = "asia-southeast1-docker.pkg.dev/vhealth-dev/vhealth-backend-dev/chat-ai:latest"
chat_ai_cpu = "1000m"
chat_ai_cpu_minimum = "500m"
chat_ai_memory = "1536Mi"
chat_ai_min_instances = 0  # On-demand for dev
chat_ai_max_instances = 3
chat_ai_timeout = 60
chat_ai_concurrency = 20
chat_ai_startup_delay = 20  # Longer for dev model loading
chat_ai_liveness_delay = 45
chat_ai_ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

# Prediction Service Configuration
prediction_image = "asia-southeast1-docker.pkg.dev/vhealth-dev/vhealth-backend-dev/prediction:latest"
prediction_cpu = "1000m"
prediction_cpu_minimum = "500m"
prediction_memory = "768Mi"
prediction_min_instances = 0  # On-demand for dev
prediction_max_instances = 2
prediction_timeout = 120
prediction_concurrency = 30
prediction_startup_delay = 10
prediction_liveness_delay = 30
prediction_ingress = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

# Model and Storage Configuration
gcp_model_bucket = "vhealth-dev-models"
qa_model_path = "models/sbert/vi-sbert-base"
prediction_model_path = "models/sklearn/health-prediction-onnx"

# Database Configuration
database_url = "postgresql://app_user:password@34.87.214.170:5432/health_management?sslmode=require"
redis_url = "redis://vhealth-cache-dev:6379"

# Service Communication
enable_reverse_communication = false  # Security: Main API orchestrates all communication
enable_debug_access = true  # Enable debug access for dev
enable_time_restrictions = false  # 24/7 development access

# Database Access for AI Services (enabled for dev debugging)
enable_chat_ai_db_access = true
enable_prediction_db_access = true

# Application Configuration
debug_enabled = true
log_level = "DEBUG"
health_check_path = "/health"

# Monitoring and Alerting
enable_monitoring = true
enable_alerting = true
notification_channel_id = "projects/vhealth-dev/notificationChannels/1234567890123456789"  # Update with actual channel ID

# Cost Optimization Settings
enable_redis_cache = true

# Legacy Configuration (for backward compatibility)
# These variables may be referenced by existing modules during migration
artifact_registry_repository_id = "vhealth-backend-dev"
cloud_sql_database_version = "POSTGRES_15"
cloud_sql_tier = "db-f1-micro"
cloud_sql_availability_type = "ZONAL"
cloud_sql_backup_enabled = true
cloud_sql_backup_start_time = "20:00"
cloud_sql_database_name = "health_management"
cloud_sql_deletion_protection = false

# VPC Connector Legacy Configuration
vpc_connector_name = "vhealth-vpc-conn-dev"
vpc_network = "default"
vpc_connector_ip_range = "10.8.0.0/28"
vpc_connector_machine_type = "e2-micro"

# Redis Legacy Configuration
redis_tier = "BASIC"
redis_memory_size_gb = 1

# Domain Configuration
enable_custom_domain = true
custom_domain = "dev.api.vhealth.io.vn"

# Email Configuration (for Main API)
mail_server = "smtp.gmail.com"
mail_port = "587"
mail_from = "congsynh.vo@gmail.com"
webui_url = "https://dev.vhealth.io.vn"

# Cloud Scheduler Configuration
scheduler_endpoint_url = "https://dev.api.vhealth.io.vn/api/v1/scheduler/hello-world"
scheduler_cron_schedule = "*/30 * * * *"
scheduler_time_zone = "Asia/Ho_Chi_Minh"
scheduler_use_oidc_auth = false
scheduler_paused = false