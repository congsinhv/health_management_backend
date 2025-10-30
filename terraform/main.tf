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
    "storage.googleapis.com",
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

# Grant Storage Object Viewer role for Q&A service files
resource "google_project_iam_member" "cloud_run_storage_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
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
    openrouter_api_key   = var.openrouter_api_key
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

# Storage bucket for Q&A service files (SBERT models, dataset, vocabulary)
module "qa_storage" {
  source = "./modules/storage_bucket"

  project_id     = var.project_id
  bucket_name    = var.qa_storage_bucket_name
  location       = var.region
  environment    = var.environment
  storage_class  = "STANDARD"
  versioning_enabled = true

  # Lifecycle rules for old versions
  lifecycle_rules = [
    {
      action = {
        type = "Delete"
        storage_class = null
      }
      condition = {
        age                   = 90
        created_before        = null
        with_state            = "ARCHIVED"
        matches_storage_class = null
        num_newer_versions    = null
      }
    }
  ]

  depends_on = [
    google_project_service.required_apis,
    google_service_account.cloud_run_sa
  ]
}

# Grant Cloud Run service account access to Q&A storage bucket
resource "google_storage_bucket_iam_member" "qa_bucket_viewer" {
  bucket = module.qa_storage.bucket_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.cloud_run_sa.email}"

  depends_on = [
    module.qa_storage,
    google_service_account.cloud_run_sa
  ]
}

