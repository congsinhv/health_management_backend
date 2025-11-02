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
  ])

  service            = each.key
  disable_on_destroy = false
}

# Create a dedicated service account for Cloud Run
resource "google_service_account" "cloud_run_sa" {
  account_id   = "vhealth-backend-${var.environment}"
  display_name = "Cloud Run Service Account for VHealth Backend - ${var.environment}"
  description  = "Service account used by Cloud Run services in ${var.environment} environment"

  depends_on = [google_project_service.required_apis]
}

resource "google_project_iam_member" "cloud_run_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"

  depends_on = [google_service_account.cloud_run_sa]
}

module "artifact_registry" {
  source = "./modules/artifact_registry"

  project_id            = var.project_id
  region                = var.region
  repository_id         = var.artifact_registry_repository_id
  environment           = var.environment
  service_account_email = google_service_account.cloud_run_sa.email

  depends_on = [
    google_project_service.required_apis,
    google_service_account.cloud_run_sa
  ]
}

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
    db_name     = module.cloud_sql.database_name
    db_username = module.cloud_sql.db_user
    db_password = module.cloud_sql.db_password
    db_host     = module.cloud_sql.public_ip_address
    # Construct DATABASE_URL for Cloud Run to connect to Cloud SQL via public IP
    # Note: Password is URL-encoded to handle special characters
    database_url         = "postgresql://${module.cloud_sql.db_user}:${urlencode(module.cloud_sql.db_password)}@${module.cloud_sql.public_ip_address}:5432/${module.cloud_sql.database_name}?sslmode=require"
    secret_key           = var.secret_key
    google_client_id     = var.google_client_id
    google_client_secret = var.google_client_secret
    mail_username        = var.mail_username
    mail_password        = var.mail_password
    # Scheduler endpoint URL - configure this to point to actual scheduled endpoint
    scheduler_endpoint_url = var.scheduler_endpoint_url
  }

  depends_on = [
    google_project_service.required_apis,
    google_service_account.cloud_run_sa,
    module.cloud_sql
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

# Create a service account for Cloud Scheduler
resource "google_service_account" "cloud_scheduler_sa" {
  account_id   = "vhealth-scheduler-${var.environment}"
  display_name = "Cloud Scheduler Service Account - ${var.environment}"
  description  = "Service account used by Cloud Scheduler to invoke Cloud Run endpoints"

  depends_on = [google_project_service.required_apis]
}

# Cloud Scheduler module for periodic tasks
module "cloud_scheduler" {
  source = "./modules/cloud_scheduler"

  project_id     = var.project_id
  region         = var.region
  environment    = var.environment
  job_name       = "vhealth-scheduler-${var.environment}"
  description    = "Periodic task that runs every 30 minutes - ${var.environment}"
  schedule       = var.scheduler_cron_schedule
  time_zone      = var.scheduler_time_zone
  http_target_uri = var.scheduler_endpoint_url
  http_method    = "POST"
  http_headers = {
    "Content-Type" = "application/json"
  }
  
  # Enable OIDC authentication if Cloud Run requires authentication
  oidc_token            = var.scheduler_use_oidc_auth
  service_account_email = var.scheduler_use_oidc_auth ? google_service_account.cloud_scheduler_sa.email : null
  
  # Retry configuration
  retry_config = {
    retry_count          = 3
    max_retry_duration   = "0s"
    min_backoff_duration = "5s"
    max_backoff_duration = "3600s"
    max_doublings        = 5
  }
  
  paused = var.scheduler_paused

  depends_on = [
    google_project_service.required_apis,
    google_service_account.cloud_scheduler_sa
  ]
}

