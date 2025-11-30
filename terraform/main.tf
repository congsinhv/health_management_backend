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

# Enable all required Google Cloud APIs
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
    "storage.googleapis.com",
    "redis.googleapis.com",
    "monitoring.googleapis.com",
    "cloudtrace.googleapis.com",
    "errorreporting.googleapis.com"
  ])

  service            = each.key
  disable_on_destroy = false
}

# VPC Network for Direct VPC Egress
module "vpc_network" {
  source = "./modules/vpc_network"

  project_id                     = var.project_id
  environment                    = var.environment
  region                         = var.region
  subnet_cidr                    = var.subnet_cidr
  use_vpc_connector              = var.use_vpc_connector_fallback
  connector_cidr                 = var.vpc_connector_cidr
  connector_min_instances        = var.vpc_connector_min_instances
  connector_max_instances        = var.vpc_connector_max_instances
  enable_private_service_connect = var.enable_private_service_connect

  depends_on = [google_project_service.required_apis]
}

# Service Accounts for Microservices
module "service_accounts" {
  source = "./modules/service_accounts"

  project_id                  = var.project_id
  environment                 = var.environment
  region                      = var.region
  title_case_environment      = var.title_case_environment
  openai_secret_id            = var.openai_secret_id
  app_secrets_id              = var.app_secrets_id
  enable_chat_ai_db_access    = var.enable_chat_ai_db_access
  enable_prediction_db_access = var.enable_prediction_db_access

  depends_on = [google_project_service.required_apis]
}

# Existing Cloud SQL Database (managed separately)
data "google_sql_database_instance" "existing" {
  count   = var.use_existing_cloud_sql ? 1 : 0
  name    = var.cloud_sql_instance_name
  project = var.project_id
  region  = var.region
}

# Existing Redis/Memorystore (managed separately)
data "google_redis_instance" "existing" {
  count   = var.use_existing_redis ? 1 : 0
  name    = var.redis_instance_name
  project = var.project_id
  region  = var.region
}

# Main API Service
module "main_api_service" {
  source = "./modules/cloud_run"

  project_id            = var.project_id
  region                = var.region
  service_name          = "${var.environment}-main-api"
  image                 = var.main_api_image
  service_account_email = module.service_accounts.main_api_email
  environment           = var.environment

  # Direct VPC Egress Configuration
  use_direct_vpc_egress = true
  vpc_network_id        = module.vpc_network.network_id
  vpc_subnet_id         = module.vpc_network.subnet_id

  # Resource Configuration
  cpu_limit        = var.main_api_cpu
  cpu_minimum      = var.main_api_cpu_minimum
  memory_limit     = var.main_api_memory
  min_instances    = var.main_api_min_instances
  max_instances    = var.main_api_max_instances
  timeout_seconds  = var.main_api_timeout
  concurrency      = var.main_api_concurrency
  session_affinity = false

  # Database Configuration
  cloud_sql_connection_name = var.use_existing_cloud_sql ? data.google_sql_database_instance.existing[0].connection_name : null
  database_url              = var.database_url
  redis_url                 = var.use_existing_redis ? data.google_redis_instance.existing[0].host : var.redis_url

  # Service URLs for Inter-Service Communication
  chat_ai_url    = module.chat_ai_service.service_url
  prediction_url = module.prediction_service.service_url

  # Health Check Configuration
  health_check_path      = var.health_check_path
  startup_delay_seconds  = var.main_api_startup_delay
  liveness_delay_seconds = var.main_api_liveness_delay

  # Environment Variables
  env_vars = merge(
    var.main_api_env_vars,
    {
      CHAT_AI_SERVICE_URL    = module.chat_ai_service.service_url
      PREDICTION_SERVICE_URL = module.prediction_service.service_url
      DATABASE_URL           = var.database_url
      REDIS_URL              = var.use_existing_redis ? "${data.google_redis_instance.existing[0].host}:${data.google_redis_instance.existing[0].port}" : var.redis_url
      DEBUG                  = var.debug_enabled ? "true" : "false"
      LOG_LEVEL              = var.log_level
    }
  )

  # Secrets
  secret_env_vars = {
    SECRET_KEY           = var.app_secrets_id
    OPENAI_API_KEY       = var.openai_secret_id
    GOOGLE_CLIENT_ID     = var.google_client_secret_id
    GOOGLE_CLIENT_SECRET = var.google_client_secret_id
  }

  # Traffic Configuration
  ingress             = var.main_api_ingress
  allow_public_access = true
  custom_domain       = var.main_api_custom_domain

  additional_labels = {
    service_type = "main-api"
    component    = "api"
  }

  depends_on = [
    google_project_service.required_apis,
    module.vpc_network,
    module.service_accounts
  ]
}

# Chat AI Service
module "chat_ai_service" {
  source = "./modules/cloud_run"

  project_id            = var.project_id
  region                = var.region
  service_name          = "${var.environment}-chat-ai"
  image                 = var.chat_ai_image
  service_account_email = module.service_accounts.chat_ai_email
  environment           = var.environment

  # Direct VPC Egress Configuration
  use_direct_vpc_egress = true
  vpc_network_id        = module.vpc_network.network_id
  vpc_subnet_id         = module.vpc_network.subnet_id

  # Resource Configuration
  cpu_limit        = var.chat_ai_cpu
  cpu_minimum      = var.chat_ai_cpu_minimum
  memory_limit     = var.chat_ai_memory
  min_instances    = var.chat_ai_min_instances
  max_instances    = var.chat_ai_max_instances
  timeout_seconds  = var.chat_ai_timeout
  concurrency      = var.chat_ai_concurrency
  session_affinity = true # For stateful conversations

  # Database Configuration (optional)
  redis_url = var.use_existing_redis ? "${data.google_redis_instance.existing[0].host}:${data.google_redis_instance.existing[0].port}" : var.redis_url

  # Service URLs
  main_api_url = module.main_api_service.service_url

  # Health Check Configuration
  health_check_path      = var.health_check_path
  startup_delay_seconds  = var.chat_ai_startup_delay
  liveness_delay_seconds = var.chat_ai_liveness_delay

  # Environment Variables
  env_vars = merge(
    var.chat_ai_env_vars,
    {
      REDIS_URL           = var.use_existing_redis ? "${data.google_redis_instance.existing[0].host}:${data.google_redis_instance.existing[0].port}" : var.redis_url
      MAIN_API_URL        = module.main_api_service.service_url
      QA_MODEL_PATH       = var.qa_model_path
      GCP_MODEL_BUCKET    = var.gcp_model_bucket
      MODEL_AUTO_DOWNLOAD = "true"
      DEBUG               = var.debug_enabled ? "true" : "false"
      LOG_LEVEL           = var.log_level
    }
  )

  # Secrets
  secret_env_vars = {
    OPENAI_API_KEY = var.openai_secret_id
  }

  # Traffic Configuration
  ingress             = var.chat_ai_ingress
  allow_public_access = false # Only accessible via Main API
  custom_domain       = null

  additional_labels = {
    service_type = "chat-ai"
    component    = "ai"
  }

  depends_on = [
    google_project_service.required_apis,
    module.vpc_network,
    module.service_accounts,
    module.main_api_service
  ]
}

# Prediction Service
module "prediction_service" {
  source = "./modules/cloud_run"

  project_id            = var.project_id
  region                = var.region
  service_name          = "${var.environment}-prediction"
  image                 = var.prediction_image
  service_account_email = module.service_accounts.prediction_email
  environment           = var.environment

  # Direct VPC Egress Configuration
  use_direct_vpc_egress = true
  vpc_network_id        = module.vpc_network.network_id
  vpc_subnet_id         = module.vpc_network.subnet_id

  # Resource Configuration
  cpu_limit        = var.prediction_cpu
  cpu_minimum      = var.prediction_cpu_minimum
  memory_limit     = var.prediction_memory
  min_instances    = var.prediction_min_instances # 0 for on-demand
  max_instances    = var.prediction_max_instances
  timeout_seconds  = var.prediction_timeout
  concurrency      = var.prediction_concurrency
  session_affinity = false

  # Database Configuration (optional)
  redis_url = var.use_existing_redis ? "${data.google_redis_instance.existing[0].host}:${data.google_redis_instance.existing[0].port}" : var.redis_url

  # Service URLs
  main_api_url = module.main_api_service.service_url

  # Health Check Configuration
  health_check_path      = var.health_check_path
  startup_delay_seconds  = var.prediction_startup_delay
  liveness_delay_seconds = var.prediction_liveness_delay

  # Environment Variables
  env_vars = merge(
    var.prediction_env_vars,
    {
      REDIS_URL             = var.use_existing_redis ? "${data.google_redis_instance.existing[0].host}:${data.google_redis_instance.existing[0].port}" : var.redis_url
      MAIN_API_URL          = module.main_api_service.service_url
      PREDICTION_MODEL_PATH = var.prediction_model_path
      GCP_MODEL_BUCKET      = var.gcp_model_bucket
      MODEL_AUTO_DOWNLOAD   = "true"
      DEBUG                 = var.debug_enabled ? "true" : "false"
      LOG_LEVEL             = var.log_level
    }
  )

  # Secrets
  secret_env_vars = {
    OPENAI_API_KEY = var.openai_secret_id
  }

  # Traffic Configuration
  ingress             = var.prediction_ingress
  allow_public_access = false # Only accessible via Main API
  custom_domain       = null

  additional_labels = {
    service_type = "prediction"
    component    = "ml"
  }

  depends_on = [
    google_project_service.required_apis,
    module.vpc_network,
    module.service_accounts,
    module.main_api_service
  ]
}

# IAM Bindings for Service-to-Service Communication
module "iam_bindings" {
  source = "./modules/iam_bindings"

  project_id                   = var.project_id
  region                       = var.region
  main_api_sa_email            = module.service_accounts.main_api_email
  chat_ai_sa_email             = module.service_accounts.chat_ai_email
  prediction_sa_email          = module.service_accounts.prediction_email
  main_api_service_name        = module.main_api_service.service_name
  chat_ai_service_name         = module.chat_ai_service.service_name
  prediction_service_name      = module.prediction_service.service_name
  enable_reverse_communication = var.enable_reverse_communication
  enable_debug_access          = var.enable_debug_access
  enable_time_restrictions     = var.enable_time_restrictions

  main_api_service_dependency   = module.main_api_service.service
  chat_ai_service_dependency    = module.chat_ai_service.service
  prediction_service_dependency = module.prediction_service.service

  depends_on = [
    module.main_api_service,
    module.chat_ai_service,
    module.prediction_service
  ]
}

# Monitoring Dashboard
module "monitoring" {
  count  = var.enable_monitoring ? 1 : 0
  source = "./modules/monitoring"

  project_id  = var.project_id
  environment = var.environment
  services = {
    main_api = {
      service_name = module.main_api_service.service_name
      display_name = "Main API"
    }
    chat_ai = {
      service_name = module.chat_ai_service.service_name
      display_name = "Chat AI"
    }
    prediction = {
      service_name = module.prediction_service.service_name
      display_name = "Prediction"
    }
  }

  depends_on = [
    module.main_api_service,
    module.chat_ai_service,
    module.prediction_service
  ]
}

# Alert Policies
module "alert_policies" {
  count  = var.enable_alerting ? 1 : 0
  source = "./modules/alert_policies"

  project_id              = var.project_id
  environment             = var.environment
  notification_channel_id = var.notification_channel_id
  services = {
    main_api = {
      service_name         = module.main_api_service.service_name
      error_rate_threshold = 0.05 # 5%
      latency_threshold_ms = 2000
    }
    chat_ai = {
      service_name         = module.chat_ai_service.service_name
      error_rate_threshold = 0.08 # 8%
      latency_threshold_ms = 5000
    }
    prediction = {
      service_name         = module.prediction_service.service_name
      error_rate_threshold = 0.06 # 6%
      latency_threshold_ms = 3000
    }
  }

  depends_on = [
    module.main_api_service,
    module.chat_ai_service,
    module.prediction_service
  ]
}