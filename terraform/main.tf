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
    # Backend configuration will be provided via backend-config file or CLI
    # bucket = "your-terraform-state-bucket"
    # prefix = "terraform/state"
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

# Enable required GCP APIs
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
  ])

  service            = each.key
  disable_on_destroy = false
}

# Create a dedicated service account for Cloud Run
resource "google_service_account" "cloud_run_sa" {
  account_id   = "cloud-run-${var.environment}"
  display_name = "Cloud Run Service Account for ${var.environment}"
  description  = "Service account used by Cloud Run services in ${var.environment} environment"

  depends_on = [google_project_service.required_apis]
}

# Grant Cloud SQL Client role to the service account
resource "google_project_iam_member" "cloud_run_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"

  depends_on = [google_service_account.cloud_run_sa]
}

# Artifact Registry Module
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

# VPC Connector Module
module "vpc_connector" {
  source = "./modules/vpc_connector"

  project_id       = var.project_id
  region           = var.region
  connector_name   = var.vpc_connector_name
  vpc_network      = var.vpc_network
  ip_cidr_range    = var.vpc_connector_ip_range
  min_instances    = var.vpc_connector_min_instances
  max_instances    = var.vpc_connector_max_instances
  machine_type     = var.vpc_connector_machine_type
  environment      = var.environment

  depends_on = [google_project_service.required_apis]
}

# Secret Manager Module
module "secret_manager" {
  source = "./modules/secret_manager"

  project_id            = var.project_id
  environment           = var.environment
  service_account_email = google_service_account.cloud_run_sa.email
  secrets = {
    database_url            = var.database_url
    secret_key             = var.secret_key
    google_client_id       = var.google_client_id
    google_client_secret   = var.google_client_secret
    mail_username          = var.mail_username
    mail_password          = var.mail_password
  }

  depends_on = [
    google_project_service.required_apis,
    google_service_account.cloud_run_sa
  ]
}

# Cloud SQL Module
module "cloud_sql" {
  source = "./modules/cloud_sql"

  project_id                = var.project_id
  region                    = var.region
  instance_name             = var.cloud_sql_instance_name
  database_version          = var.cloud_sql_database_version
  tier                      = var.cloud_sql_tier
  availability_type         = var.cloud_sql_availability_type
  backup_enabled            = var.cloud_sql_backup_enabled
  backup_start_time         = var.cloud_sql_backup_start_time
  database_name             = var.cloud_sql_database_name
  deletion_protection       = var.cloud_sql_deletion_protection
  vpc_network              = var.vpc_network
  private_ip_address_name   = var.cloud_sql_private_ip_name
  environment              = var.environment

  depends_on = [
    google_project_service.required_apis,
    module.vpc_connector
  ]
}

# Cloud Run Module
module "cloud_run" {
  source = "./modules/cloud_run"

  project_id                = var.project_id
  region                    = var.region
  service_name              = var.cloud_run_service_name
  image                     = var.cloud_run_image
  environment               = var.environment
  service_account_email     = google_service_account.cloud_run_sa.email
  vpc_connector_id          = module.vpc_connector.connector_id
  cloud_sql_connection_name = module.cloud_sql.connection_name
  
  # Resource limits
  cpu_limit                 = var.cloud_run_cpu_limit
  memory_limit              = var.cloud_run_memory_limit
  max_instances             = var.cloud_run_max_instances
  min_instances             = var.cloud_run_min_instances
  timeout_seconds           = var.cloud_run_timeout_seconds
  concurrency               = var.cloud_run_concurrency
  
  # Environment variables from secrets
  secret_env_vars = {
    DATABASE_URL         = module.secret_manager.secret_versions["database_url"]
    SECRET_KEY          = module.secret_manager.secret_versions["secret_key"]
    GOOGLE_CLIENT_ID    = module.secret_manager.secret_versions["google_client_id"]
    GOOGLE_CLIENT_SECRET = module.secret_manager.secret_versions["google_client_secret"]
    MAIL_USERNAME       = module.secret_manager.secret_versions["mail_username"]
    MAIL_PASSWORD       = module.secret_manager.secret_versions["mail_password"]
  }

  # Additional environment variables
  env_vars = {
    DEBUG                    = var.debug
    LOG_LEVEL               = var.log_level
    APP_NAME                = var.app_name
    APP_VERSION             = var.app_version
    MAIL_SERVER             = var.mail_server
    MAIL_PORT               = var.mail_port
    MAIL_FROM               = var.mail_from
    WEBUI_URL               = var.webui_url
  }

  depends_on = [
    google_service_account.cloud_run_sa,
    module.vpc_connector,
    module.cloud_sql,
    module.secret_manager,
    module.artifact_registry
  ]
}
