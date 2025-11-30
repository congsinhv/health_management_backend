# Phase 4: Infrastructure Updates

**Phase:** 4 of 5
**Duration:** 2-3 days
**Priority:** High
**Status:** Not Started
**Dependencies:** Phase 3 (Prediction Service Extraction)

## Context

**Research Reports:**
- [GCP Microservices](./research/researcher-01-gcp-microservices.md) - Direct VPC Egress, service accounts, IAM roles
- [System Architecture](../../docs/system-architecture.md) - Current Terraform setup

**Current Infrastructure:**
- Single Cloud Run service (main-api)
- Terraform manages: Cloud Run, Cloud SQL, Redis, VPC Connector, GCS
- Jenkins pipeline: Single deployment job
- Environment: dev, prod

## Overview

Update Terraform configuration for 3 Cloud Run services, create separate Jenkins pipelines, configure service-to-service IAM authentication, migrate to Direct VPC Egress (from VPC Connector), and set up monitoring/alerting for microservices architecture.

## Key Insights from Research

**Direct VPC Egress (Researcher-01):**
- Preferred over VPC Connector for 2024+
- Lower latency (2-5ms vs 8-15ms)
- No monthly VPC Connector fees
- Better throughput and reliability

**Service Accounts:**
- Each service has dedicated user-managed service account
- IAM roles for Cloud Run invocation
- Audit trail via Cloud Audit Logs

**Min Instance Strategy:**
- Main API: 2 min instances (always-on CRUD)
- Chat AI: 1 min instance (warm for Q&A requests)
- Prediction: 0 min instances (on-demand async)

## Requirements

**Terraform Modules to Update:**
```
terraform/
├── modules/
│   ├── cloud_run/           # Update for 3 services
│   ├── vpc_network/          # NEW - Direct VPC Egress setup
│   ├── service_accounts/     # NEW - Service accounts module
│   └── iam_bindings/         # NEW - Service-to-service IAM
├── environments/
│   ├── dev.tfvars           # 3 services config
│   └── prod.tfvars          # 3 services config
└── main.tf                  # Update for microservices
```

**Jenkins Pipelines:**
```
Jenkinsfile.main-api         # Main API deployment
Jenkinsfile.chat-ai          # Chat AI deployment
Jenkinsfile.prediction       # Prediction deployment
Jenkinsfile.all-services     # Deploy all (orchestration)
```

**Environment Variables per Service:**
- Main API: DATABASE_URL, REDIS_URL, CHAT_AI_URL, PREDICTION_URL
- Chat AI: OPENAI_API_KEY, REDIS_URL (optional), QA_MODEL_PATH
- Prediction: OPENAI_API_KEY, PREDICTION_MODEL_PATH

## Architecture Changes

**Before:**
```
Terraform:
  └── Cloud Run (main-api) → VPC Connector → Cloud SQL/Redis

Jenkins:
  └── Single pipeline → Build → Deploy main-api
```

**After:**
```
Terraform:
  ├── Cloud Run (main-api) ────┐
  ├── Cloud Run (chat-ai)   ────┼→ Direct VPC Egress → Cloud SQL/Redis
  ├── Cloud Run (prediction) ───┘
  ├── Service Accounts (3)
  └── IAM Bindings (service-to-service)

Jenkins:
  ├── Pipeline: main-api
  ├── Pipeline: chat-ai
  ├── Pipeline: prediction
  └── Pipeline: all-services (orchestrator)
```

**Network Architecture:**
```
Internet → Load Balancer
              ↓
         Main API Service (VPC Network)
              ↓ (Direct VPC Egress)
         Cloud SQL, Redis (Private IPs)

Main API ←→ Chat AI (IAM + Direct VPC Egress)
Main API ←→ Prediction (IAM + Direct VPC Egress)
```

## Related Files

**Terraform Files to Update:**
- `terraform/main.tf` - Add 2 new Cloud Run services
- `terraform/modules/cloud_run/` - Multi-service support
- `terraform/environments/dev.tfvars` - 3 services config
- `terraform/environments/prod.tfvars` - 3 services config

**Terraform Files to Create:**
- `terraform/modules/vpc_network/main.tf` - Direct VPC Egress
- `terraform/modules/service_accounts/main.tf`
- `terraform/modules/iam_bindings/main.tf`

**Jenkins Files to Create:**
- `Jenkinsfile.main-api`
- `Jenkinsfile.chat-ai`
- `Jenkinsfile.prediction`
- `Jenkinsfile.all-services`

## Implementation Steps

### 1. Create VPC Network Module (Day 1)

**1.1 Direct VPC Egress Setup:**
```hcl
# terraform/modules/vpc_network/main.tf
"""VPC network for Direct VPC Egress."""

resource "google_compute_network" "vpc_network" {
  name                    = "${var.environment}-vpc"
  auto_create_subnetworks = false
  project                 = var.project_id
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${var.environment}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.vpc_network.id

  # Private Google Access for Cloud SQL/Redis
  private_ip_google_access = true
}

# Serverless VPC Access Connector (for backward compatibility)
# Will be deprecated after migration to Direct VPC Egress
resource "google_vpc_access_connector" "connector" {
  count = var.use_vpc_connector ? 1 : 0

  name          = "${var.environment}-vpc-connector"
  region        = var.region
  network       = google_compute_network.vpc_network.id
  ip_cidr_range = var.connector_cidr

  lifecycle {
    create_before_destroy = true
  }
}

output "network_id" {
  value = google_compute_network.vpc_network.id
}

output "subnet_id" {
  value = google_compute_subnetwork.subnet.id
}
```

### 2. Create Service Accounts Module (Day 1)

```hcl
# terraform/modules/service_accounts/main.tf
"""Service accounts for microservices."""

# Main API Service Account
resource "google_service_account" "main_api" {
  account_id   = "${var.environment}-main-api-sa"
  display_name = "Main API Service Account"
  project      = var.project_id
}

# Chat AI Service Account
resource "google_service_account" "chat_ai" {
  account_id   = "${var.environment}-chat-ai-sa"
  display_name = "Chat AI Service Account"
  project      = var.project_id
}

# Prediction Service Account
resource "google_service_account" "prediction" {
  account_id   = "${var.environment}-prediction-sa"
  display_name = "Prediction Service Account"
  project      = var.project_id
}

# Grant Cloud SQL Client role to services that need it
resource "google_project_iam_member" "main_api_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.main_api.email}"
}

# Grant Secret Manager access to all services
resource "google_secret_manager_secret_iam_member" "openai_key_access" {
  for_each = toset([
    google_service_account.main_api.email,
    google_service_account.chat_ai.email,
    google_service_account.prediction.email
  ])

  secret_id = var.openai_secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${each.value}"
}

output "main_api_email" {
  value = google_service_account.main_api.email
}

output "chat_ai_email" {
  value = google_service_account.chat_ai.email
}

output "prediction_email" {
  value = google_service_account.prediction.email
}
```

### 3. Create IAM Bindings Module (Day 1)

```hcl
# terraform/modules/iam_bindings/main.tf
"""IAM bindings for service-to-service communication."""

# Main API can invoke Chat AI
resource "google_cloud_run_service_iam_member" "main_api_to_chat_ai" {
  service  = var.chat_ai_service_name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.main_api_sa_email}"
}

# Main API can invoke Prediction
resource "google_cloud_run_service_iam_member" "main_api_to_prediction" {
  service  = var.prediction_service_name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${var.main_api_sa_email}"
}

# Allow public access to Main API (external users)
resource "google_cloud_run_service_iam_member" "main_api_public" {
  service  = var.main_api_service_name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "bindings_created" {
  value = {
    main_to_chat_ai    = google_cloud_run_service_iam_member.main_api_to_chat_ai.id
    main_to_prediction = google_cloud_run_service_iam_member.main_api_to_prediction.id
  }
}
```

### 4. Update Cloud Run Module (Day 1-2)

```hcl
# terraform/modules/cloud_run/main.tf
"""Cloud Run service with Direct VPC Egress support."""

resource "google_cloud_run_v2_service" "service" {
  name     = var.service_name
  location = var.region
  project  = var.project_id

  template {
    service_account = var.service_account_email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
      }

      # Environment variables
      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      # Secrets from Secret Manager
      dynamic "env" {
        for_each = var.secrets
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value.secret_name
              version = env.value.version
            }
          }
        }
      }
    }

    # Direct VPC Egress (preferred)
    vpc_access {
      egress = "ALL_TRAFFIC"  # Route all traffic through VPC
      network_interfaces {
        network    = var.vpc_network_id
        subnetwork = var.vpc_subnet_id
      }
    }

    timeout = "${var.timeout}s"
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }
}

output "service_url" {
  value = google_cloud_run_v2_service.service.uri
}

output "service_name" {
  value = google_cloud_run_v2_service.service.name
}
```

### 5. Update Main Terraform Configuration (Day 2)

```hcl
# terraform/main.tf
"""Main Terraform configuration for microservices."""

# VPC Network
module "vpc_network" {
  source = "./modules/vpc_network"

  project_id    = var.gcp_project_id
  environment   = var.environment
  region        = var.region
  subnet_cidr   = var.subnet_cidr
}

# Service Accounts
module "service_accounts" {
  source = "./modules/service_accounts"

  project_id       = var.gcp_project_id
  environment      = var.environment
  openai_secret_id = var.openai_secret_id
}

# Main API Service
module "main_api_service" {
  source = "./modules/cloud_run"

  service_name         = "${var.environment}-main-api"
  project_id           = var.gcp_project_id
  region               = var.region
  image                = var.main_api_image
  service_account_email = module.service_accounts.main_api_email

  cpu          = var.main_api_cpu
  memory       = var.main_api_memory
  min_instances = var.main_api_min_instances
  max_instances = var.main_api_max_instances
  timeout      = 300

  vpc_network_id = module.vpc_network.network_id
  vpc_subnet_id  = module.vpc_network.subnet_id

  env_vars = {
    DATABASE_URL         = var.database_url
    REDIS_URL            = var.redis_url
    CHAT_AI_SERVICE_URL  = module.chat_ai_service.service_url
    PREDICTION_SERVICE_URL = module.prediction_service.service_url
    DEBUG                = var.debug
  }

  secrets = {
    SECRET_KEY = {
      secret_name = var.secret_key_secret_id
      version     = "latest"
    }
  }
}

# Chat AI Service
module "chat_ai_service" {
  source = "./modules/cloud_run"

  service_name         = "${var.environment}-chat-ai"
  project_id           = var.gcp_project_id
  region               = var.region
  image                = var.chat_ai_image
  service_account_email = module.service_accounts.chat_ai_email

  cpu          = var.chat_ai_cpu
  memory       = var.chat_ai_memory
  min_instances = var.chat_ai_min_instances
  max_instances = var.chat_ai_max_instances
  timeout      = 60

  vpc_network_id = module.vpc_network.network_id
  vpc_subnet_id  = module.vpc_network.subnet_id

  env_vars = {
    REDIS_URL           = var.redis_url
    QA_MODEL_PATH       = var.qa_model_path
    GCP_MODEL_BUCKET    = var.gcp_model_bucket
    MODEL_AUTO_DOWNLOAD = "true"
  }

  secrets = {
    OPENAI_API_KEY = {
      secret_name = var.openai_secret_id
      version     = "latest"
    }
  }
}

# Prediction Service
module "prediction_service" {
  source = "./modules/cloud_run"

  service_name         = "${var.environment}-prediction"
  project_id           = var.gcp_project_id
  region               = var.region
  image                = var.prediction_image
  service_account_email = module.service_accounts.prediction_email

  cpu          = var.prediction_cpu
  memory       = var.prediction_memory
  min_instances = var.prediction_min_instances  # 0 for on-demand
  max_instances = var.prediction_max_instances
  timeout      = 120

  vpc_network_id = module.vpc_network.network_id
  vpc_subnet_id  = module.vpc_network.subnet_id

  env_vars = {
    PREDICTION_MODEL_PATH = var.prediction_model_path
    GCP_MODEL_BUCKET      = var.gcp_model_bucket
  }

  secrets = {
    OPENAI_API_KEY = {
      secret_name = var.openai_secret_id
      version     = "latest"
    }
  }
}

# IAM Bindings
module "iam_bindings" {
  source = "./modules/iam_bindings"

  region                  = var.region
  main_api_sa_email       = module.service_accounts.main_api_email
  main_api_service_name   = module.main_api_service.service_name
  chat_ai_service_name    = module.chat_ai_service.service_name
  prediction_service_name = module.prediction_service.service_name
}
```

**Environment Config:**
```hcl
# terraform/environments/prod.tfvars
environment = "prod"
gcp_project_id = "vhealth-prod"
region = "asia-southeast1"

# Network
subnet_cidr = "10.8.0.0/28"

# Main API
main_api_image = "gcr.io/vhealth-prod/main-api:latest"
main_api_cpu = "1"
main_api_memory = "512Mi"
main_api_min_instances = 2
main_api_max_instances = 50

# Chat AI
chat_ai_image = "gcr.io/vhealth-prod/chat-ai:latest"
chat_ai_cpu = "1"
chat_ai_memory = "1536Mi"
chat_ai_min_instances = 1
chat_ai_max_instances = 20

# Prediction
prediction_image = "gcr.io/vhealth-prod/prediction:latest"
prediction_cpu = "1"
prediction_memory = "768Mi"
prediction_min_instances = 0  # On-demand
prediction_max_instances = 10
```

### 6. Create Jenkins Pipelines (Day 2-3)

**6.1 Main API Pipeline:**
```groovy
// Jenkinsfile.main-api
pipeline {
    agent any

    parameters {
        choice(name: 'ENVIRONMENT', choices: ['dev', 'prod'], description: 'Environment')
        string(name: 'IMAGE_TAG', defaultValue: 'latest', description: 'Docker image tag')
    }

    stages {
        stage('Build Main API') {
            steps {
                sh """
                    docker build -t gcr.io/${GCP_PROJECT}/main-api:${params.IMAGE_TAG} .
                    docker push gcr.io/${GCP_PROJECT}/main-api:${params.IMAGE_TAG}
                """
            }
        }

        stage('Update Terraform') {
            steps {
                sh """
                    cd terraform
                    terraform workspace select ${params.ENVIRONMENT}
                    terraform apply -var='main_api_image=gcr.io/${GCP_PROJECT}/main-api:${params.IMAGE_TAG}' -auto-approve
                """
            }
        }

        stage('Smoke Tests') {
            steps {
                sh """
                    curl -f \${MAIN_API_URL}/health || exit 1
                """
            }
        }
    }
}
```

**6.2 All Services Pipeline (Orchestrator):**
```groovy
// Jenkinsfile.all-services
pipeline {
    agent any

    parameters {
        choice(name: 'ENVIRONMENT', choices: ['dev', 'prod'], description: 'Environment')
    }

    stages {
        stage('Build All Services') {
            parallel {
                stage('Build Main API') {
                    steps {
                        build job: 'main-api-build', parameters: [
                            string(name: 'ENVIRONMENT', value: params.ENVIRONMENT)
                        ]
                    }
                }
                stage('Build Chat AI') {
                    steps {
                        build job: 'chat-ai-build', parameters: [
                            string(name: 'ENVIRONMENT', value: params.ENVIRONMENT)
                        ]
                    }
                }
                stage('Build Prediction') {
                    steps {
                        build job: 'prediction-build', parameters: [
                            string(name: 'ENVIRONMENT', value: params.ENVIRONMENT)
                        ]
                    }
                }
            }
        }

        stage('Deploy Infrastructure') {
            steps {
                sh """
                    cd terraform
                    terraform workspace select ${params.ENVIRONMENT}
                    terraform plan -out=tfplan
                    terraform apply tfplan
                """
            }
        }

        stage('Smoke Tests') {
            steps {
                sh """
                    # Test Main API
                    curl -f \${MAIN_API_URL}/health

                    # Test Chat AI
                    curl -f \${CHAT_AI_URL}/health

                    # Test Prediction
                    curl -f \${PREDICTION_URL}/health
                """
            }
        }
    }
}
```

### 7. Monitoring and Alerting (Day 3)

**7.1 Create Monitoring Dashboard:**
```hcl
# terraform/modules/monitoring/main.tf
resource "google_monitoring_dashboard" "microservices" {
  dashboard_json = jsonencode({
    displayName = "${var.environment} Microservices Dashboard"
    gridLayout = {
      widgets = [
        {
          title = "Main API Request Rate"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.environment}-main-api\""
                  aggregation = { alignmentPeriod = "60s" }
                }
              }
            }]
          }
        },
        {
          title = "Chat AI Latency"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.environment}-chat-ai\""
                  aggregation = { alignmentPeriod = "60s" }
                }
              }
            }]
          }
        },
        {
          title = "Prediction Cold Starts"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.environment}-prediction\""
                  aggregation = { alignmentPeriod = "60s" }
                }
              }
            }]
          }
        }
      ]
    }
  })
}
```

**7.2 Create Alert Policies:**
```hcl
# Alert: High error rate
resource "google_monitoring_alert_policy" "high_error_rate" {
  display_name = "${var.environment} High Error Rate"
  combiner     = "OR"

  conditions {
    display_name = "Error rate > 5%"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0.05

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }

  notification_channels = [var.notification_channel_id]
}

# Alert: High latency
resource "google_monitoring_alert_policy" "high_latency" {
  display_name = "${var.environment} High Latency"
  combiner     = "OR"

  conditions {
    display_name = "P95 latency > 2s"

    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\""
      duration        = "120s"
      comparison      = "COMPARISON_GT"
      threshold_value = 2000

      aggregations {
        alignment_period     = "60s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_PERCENTILE_95"
      }
    }
  }

  notification_channels = [var.notification_channel_id]
}
```

## Todo List

- [ ] Create VPC network module with Direct VPC Egress
- [ ] Create service accounts module (3 accounts)
- [ ] Create IAM bindings module (service-to-service)
- [ ] Update Cloud Run module for Direct VPC Egress
- [ ] Update main.tf with 3 Cloud Run services
- [ ] Create prod.tfvars with microservices config
- [ ] Create dev.tfvars with microservices config
- [ ] Test Terraform plan in dev environment
- [ ] Apply Terraform in dev environment
- [ ] Verify network connectivity (Direct VPC Egress)
- [ ] Create Jenkinsfile.main-api
- [ ] Create Jenkinsfile.chat-ai
- [ ] Create Jenkinsfile.prediction
- [ ] Create Jenkinsfile.all-services (orchestrator)
- [ ] Create monitoring dashboard in Terraform
- [ ] Create alert policies (error rate, latency, cold starts)
- [ ] Test Jenkins pipeline for Main API
- [ ] Test Jenkins pipeline for Chat AI
- [ ] Test Jenkins pipeline for Prediction
- [ ] Run end-to-end deployment test
- [ ] Validate service-to-service IAM authentication
- [ ] Document Terraform changes in deployment guide

## Success Criteria

**Infrastructure:**
- 3 Cloud Run services deployed successfully
- Direct VPC Egress configured (2-5ms latency)
- Service-to-service IAM auth working
- Min instances set correctly (Main=2, Chat=1, Pred=0)

**Automation:**
- Jenkins pipelines working for all 3 services
- Terraform apply completes without errors
- Monitoring dashboards created
- Alert policies configured

**Validation:**
- All health checks passing
- Service-to-service communication < 50ms
- No VPC Connector fees (migrated to Direct VPC Egress)

## Risk Assessment

**VPC Connector Migration:**
- Risk: Direct VPC Egress breaks connectivity
- Mitigation: Test in dev first; keep VPC Connector as fallback
- Rollback: Switch back to VPC Connector in Terraform

**Terraform State Conflicts:**
- Risk: Multiple pipelines modifying state simultaneously
- Mitigation: Use Terraform workspaces; lock state file
- Validation: Test pipelines sequentially first

**IAM Permission Delays:**
- Risk: IAM bindings take time to propagate
- Mitigation: Add 30s delay after IAM changes
- Validation: Retry logic in HTTP clients

## Security Considerations

**Service Account Permissions:**
- Main API: cloudsql.client, secretmanager.accessor, run.invoker (Chat AI + Prediction)
- Chat AI: secretmanager.accessor (OpenAI key)
- Prediction: secretmanager.accessor (OpenAI key)
- Least privilege principle enforced

**Network Security:**
- Direct VPC Egress routes all traffic through private network
- Cloud SQL/Redis accessible only via private IPs
- No public database endpoints

**Secret Management:**
- All secrets in Secret Manager
- IAM roles for secret access
- Automatic secret rotation supported

## Next Steps

**After Phase 4 Completion:**
- Phase 5: Load testing and optimization
- Phase 5: Blue-green deployment strategy
- Phase 5: Production rollout
