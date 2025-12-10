terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  backend "gcs" {
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

resource "google_project_service" "required_apis" {
  for_each = toset([
    "cloudresourcemanager.googleapis.com",
    "servicenetworking.googleapis.com",
    "compute.googleapis.com",
    "vpcaccess.googleapis.com",
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudscheduler.googleapis.com",
    "cloudtasks.googleapis.com",
    "storage.googleapis.com",
    "redis.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
}

# Create a dedicated service account for Cloud Run
resource "google_service_account" "cloud_run_sa" {
  account_id   = "vhealth-${var.environment}-backend"
  display_name = "VHealth Cloud Run Backend - ${var.environment}"
  description  = "Service account used by Cloud Run services in ${var.environment} environment"

  depends_on = [google_project_service.required_apis]
}

# Temporarily disabled - IAM binding managed manually to avoid permission issues
# resource "google_project_iam_member" "cloud_run_sql_client" {
#   project = var.project_id
#   role    = "roles/cloudsql.client"
#   member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
#
#   depends_on = [google_service_account.cloud_run_sa]
# }

resource "google_storage_bucket_iam_member" "cloud_run_storage_writer" {
  bucket = "vhealth-${var.environment}-public"
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloud_run_sa.email}"

  depends_on = [
    google_service_account.cloud_run_sa,
    google_project_service.required_apis
  ]
}

# Temporarily commented out due to existing resources
# module "artifact_registry" {
#   source = "./modules/artifact_registry"

#   project_id            = var.project_id
#   region                = var.region
#   repository_id         = var.artifact_registry_repository_id
#   environment           = var.environment
#   service_account_email = google_service_account.cloud_run_sa.email

#   depends_on = [
#     google_project_service.required_apis,
#     google_service_account.cloud_run_sa
#   ]
# }

module "vpc_connector" {
  source = "./modules/vpc_connector"

  project_id     = var.project_id
  region         = var.region
  connector_name = var.vpc_connector_name
  vpc_network    = var.vpc_network
  ip_cidr_range  = var.vpc_connector_ip_range
  min_instances  = var.vpc_connector_min_instances
  max_instances  = var.vpc_connector_max_instances
  machine_type   = var.vpc_connector_machine_type
  environment    = var.environment

  depends_on = [google_project_service.required_apis]
}

module "secret_manager" {
  source = "./modules/secret_manager"

  project_id            = var.project_id
  environment           = var.environment
  service_account_email = google_service_account.cloud_run_sa.email
  secrets = {
    # Database credentials stored separately for flexibility
    db_name     = "health_management" # Hardcoded since database already exists
    db_username = module.cloud_sql.db_user
    db_password = module.cloud_sql.db_password
    db_host     = module.cloud_sql.public_ip_address
    # Construct DATABASE_URL for Cloud Run to connect to Cloud SQL via public IP
    # Note: Password is URL-encoded to handle special characters
    database_url         = "postgresql://${module.cloud_sql.db_user}:${urlencode(module.cloud_sql.db_password)}@${module.cloud_sql.public_ip_address}:5432/health_management?sslmode=require"
    secret_key           = var.secret_key
    google_client_id     = var.google_client_id
    google_client_secret = var.google_client_secret
    mail_username        = var.mail_username
    mail_password        = var.mail_password
    mail_from            = var.mail_from
    mail_server          = var.mail_server
    # Scheduler endpoint URL - configure this to point to actual scheduled endpoint
    scheduler_endpoint_url = var.scheduler_endpoint_url
    # Redis connection details
    redis_host         = var.enable_redis_cache ? module.memorystore.redis_host : ""
    redis_port         = var.enable_redis_cache ? module.memorystore.redis_port : ""
    redis_auth_secret  = var.enable_redis_cache ? module.memorystore.redis_auth_secret : ""
    enable_redis_cache = var.enable_redis_cache ? "true" : "false"
  }

  depends_on = [
    google_project_service.required_apis,
    google_service_account.cloud_run_sa,
    module.cloud_sql,
    module.memorystore
  ]
}

# Grant Cloud Run service account access to pre-existing OpenAI API key secret
# This secret was created manually and is not managed by Terraform
resource "google_secret_manager_secret_iam_member" "openai_secret_access" {
  secret_id = "vhealth-${var.environment}-openai-api-key"
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_sa.email}"

  depends_on = [
    google_project_service.required_apis,
    google_service_account.cloud_run_sa
  ]
}

module "cloud_sql" {
  source = "./modules/cloud_sql"

  project_id          = var.project_id
  region              = var.region
  instance_name       = var.cloud_sql_instance_name
  database_version    = var.cloud_sql_database_version
  tier                = var.cloud_sql_tier
  availability_type   = var.cloud_sql_availability_type
  backup_enabled      = var.cloud_sql_backup_enabled
  backup_start_time   = var.cloud_sql_backup_start_time
  database_name       = var.cloud_sql_database_name
  deletion_protection = var.cloud_sql_deletion_protection
  environment         = var.environment

  depends_on = [google_project_service.required_apis]
}

# Reference existing private IP allocation (already exists in GCP)
# Note: SQL uses public IP, so this is only for Redis and other private services
data "google_compute_global_address" "private_ip_alloc" {
  name = "vhealth-${var.environment}-private-ip"
}

# Manage existing VPC peering connection
# IMPORTANT: Must be imported first: terraform import google_service_networking_connection.private_vpc_connection vhealth-dev:servicenetworking.googleapis.com:default
resource "google_service_networking_connection" "private_vpc_connection" {
  network = "projects/${var.project_id}/global/networks/${var.vpc_network}"
  service = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [
    data.google_compute_global_address.private_ip_alloc.name
  ]

  depends_on = [
    google_project_service.required_apis
  ]
}

# Provision Memorystore Redis
module "memorystore" {
  source = "./modules/memorystore"

  instance_name  = "vhealth-${var.environment}-cache"
  tier           = var.redis_tier
  memory_size_gb = var.redis_memory_size_gb
  region         = var.region
  redis_version  = var.redis_version
  display_name   = "VHealth Cache - ${var.environment}"
  vpc_network    = "projects/${var.project_id}/global/networks/${var.vpc_network}"
  environment    = var.environment

  maintenance_window_day  = var.redis_maintenance_day
  maintenance_window_hour = var.redis_maintenance_hour

  depends_on = [
    google_project_service.required_apis,
    module.vpc_connector,
    google_service_networking_connection.private_vpc_connection
  ]
}

# Grant Cloud Run SA access to Redis auth secret
resource "google_secret_manager_secret_iam_member" "redis_auth_access" {
  secret_id = module.memorystore.redis_auth_secret
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run_sa.email}"

  depends_on = [module.memorystore]
}

# Create a service account for Cloud Scheduler
resource "google_service_account" "cloud_scheduler_sa" {
  account_id   = "vhealth-${var.environment}-scheduler"
  display_name = "VHealth Cloud Scheduler - ${var.environment}"
  description  = "Service account used by Cloud Scheduler to invoke Cloud Run endpoints"

  depends_on = [google_project_service.required_apis]
}

# Grant Cloud Run invoker role to Cloud Scheduler service account
resource "google_project_iam_member" "scheduler_run_invoker" {
  count = var.enable_notification_scheduler ? 1 : 0

  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.cloud_scheduler_sa.email}"

  depends_on = [google_service_account.cloud_scheduler_sa]
}

# ============================================================================
# Cloud Tasks Module - Notification Queue
# ============================================================================
module "cloud_tasks" {
  count  = var.enable_cloud_tasks ? 1 : 0
  source = "./modules/cloud_tasks"

  project_id  = var.project_id
  location    = var.region
  queue_name  = var.cloud_tasks_queue_name
  environment = var.environment

  rate_limits = {
    max_dispatches_per_second = var.cloud_tasks_max_dispatches_per_second
    max_burst_size            = var.cloud_tasks_max_burst_size
    max_concurrent_dispatches = var.cloud_tasks_max_concurrent_dispatches
  }

  retry_config = {
    max_attempts       = var.cloud_tasks_max_attempts
    min_backoff        = var.cloud_tasks_min_backoff
    max_backoff        = var.cloud_tasks_max_backoff
    max_doublings      = var.cloud_tasks_max_doublings
    max_retry_duration = "0s"
  }

  enable_logging         = var.cloud_tasks_enable_logging
  logging_sampling_ratio = var.cloud_tasks_logging_sampling_ratio

  # Create dedicated service account for Cloud Tasks OIDC invocation
  create_service_account       = true
  service_account_id           = "vhealth-${var.environment}-tasks-invoker"
  service_account_display_name = "VHealth Cloud Tasks Invoker - ${var.environment}"
  grant_enqueuer_role          = true
  grant_run_invoker_role       = true
  grant_token_creator_role     = false

  # Allow Cloud Run SA to enqueue tasks
  cloud_run_service_account_email = google_service_account.cloud_run_sa.email

  depends_on = [
    google_project_service.required_apis,
    google_service_account.cloud_run_sa
  ]
}

# ============================================================================
# Cloud Scheduler Module - Notification Batch Processing
# ============================================================================
module "notification_scheduler" {
  count  = var.enable_notification_scheduler ? 1 : 0
  source = "./modules/cloud_scheduler"

  project_id      = var.project_id
  region          = var.region
  environment     = var.environment
  job_name        = "vhealth-${var.environment}-notification-processor"
  description     = "Process pending workout notifications every ${var.notification_scheduler_interval_minutes} minutes"
  schedule        = "*/${var.notification_scheduler_interval_minutes} * * * *"
  time_zone       = var.scheduler_time_zone
  http_target_uri = "${var.backend_url}/api/v1/notifications/process-batch"
  http_method     = "POST"
  http_headers = {
    "Content-Type" = "application/json"
  }

  # Enable OIDC authentication for Cloud Run
  oidc_token            = true
  service_account_email = google_service_account.cloud_scheduler_sa.email

  # Retry configuration
  retry_config = {
    retry_count          = 3
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "300s"
    max_doublings        = 5
  }

  paused = var.notification_scheduler_paused

  depends_on = [
    google_project_service.required_apis,
    google_service_account.cloud_scheduler_sa,
    google_project_iam_member.scheduler_run_invoker
  ]
}

