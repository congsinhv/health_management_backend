# VHealth Test Environment Setup - Complete Infrastructure Checklist

**Project**: vhealth-test
**GCP Account**: oryndrvn@gmail.com
**Region**: asia-southeast1 (Singapore)
**Date**: 2025-11-28

## Executive Summary

This document outlines complete infrastructure requirements to deploy vhealth-test environment - first deployment to new GCP account. Based on existing vhealth-prod infrastructure analysis, identified 15 core GCP services + supporting configurations needed before first deployment.

**Critical Context**: vhealth-dev no longer exists - all "dev" references replaced with "test"

---

## I. GCP PROJECT & BILLING SETUP

### 1.1 Project Configuration
- [x] Project created: vhealth-test
- [ ] **Billing account linked** - CRITICAL first step
  - Without billing: cannot enable APIs or provision resources
  - Verify: `gcloud billing projects describe vhealth-test`
- [ ] **Set default project**
  ```bash
  gcloud config set project vhealth-test
  gcloud config set compute/region asia-southeast1
  ```

### 1.2 Enable Required GCP APIs
**Must enable before Terraform runs:**
```bash
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  servicenetworking.googleapis.com \
  compute.googleapis.com \
  vpcaccess.googleapis.com \
  run.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  storage.googleapis.com \
  redis.googleapis.com
```

**Validation**:
```bash
gcloud services list --enabled --filter="name:(run.googleapis.com OR sqladmin.googleapis.com)"
```

---

## II. IAM & SERVICE ACCOUNTS

### 2.1 Cloud Run Service Account
**Purpose**: Cloud Run service identity for accessing Cloud SQL, Storage, Secrets

**Creation** (via Terraform or manual):
```bash
gcloud iam service-accounts create vhealth-backend-test \
  --display-name="Cloud Run Service Account for VHealth Backend - test" \
  --description="Service account used by Cloud Run services in test environment"
```

**Required Roles**:
- `roles/cloudsql.client` - Connect to Cloud SQL
- `roles/storage.objectAdmin` - Access GCS buckets (models, PDFs)
- `roles/secretmanager.secretAccessor` - Access Secret Manager secrets

### 2.2 Cloud Scheduler Service Account
**Purpose**: Invoke Cloud Run endpoints for scheduled tasks

```bash
gcloud iam service-accounts create vhealth-scheduler-test \
  --display-name="Cloud Scheduler Service Account - test" \
  --description="Service account used by Cloud Scheduler to invoke Cloud Run endpoints"
```

### 2.3 Terraform Service Account (for CI/CD)
**Purpose**: Jenkins/CI/CD automation

**Creation**:
```bash
gcloud iam service-accounts create vhealth-terraform \
  --display-name="Terraform Automation SA"

# Grant necessary permissions
gcloud projects add-iam-policy-binding vhealth-test \
  --member="serviceAccount:vhealth-terraform@vhealth-test.iam.gserviceaccount.com" \
  --role="roles/editor"

# Create & download key for Jenkins
gcloud iam service-accounts keys create terraform-sa-key.json \
  --iam-account=vhealth-terraform@vhealth-test.iam.gserviceaccount.com
```

**Store key in Jenkins**: Credentials → Add → Secret file → ID: `gcp-service-account-key`

---

## III. NETWORKING INFRASTRUCTURE

### 3.1 VPC Network
**Using**: `default` VPC (already exists in new GCP projects)
**Verify**: `gcloud compute networks list`

### 3.2 VPC Connector
**Purpose**: Allow Cloud Run to access private resources (Redis Memorystore)

**Terraform Configuration** (test.tfvars):
```hcl
vpc_connector_name          = "vhealth-vpc-conn-test"
vpc_network                 = "default"
vpc_connector_ip_range      = "10.9.0.0/28"  # Different from prod (10.10.0.0/28)
vpc_connector_min_instances = 2
vpc_connector_max_instances = 3
vpc_connector_machine_type  = "e2-micro"
```

**Cost**: ~$10-15/month (always running)

### 3.3 Private Service Connection
**Purpose**: VPC peering for private IP allocation (used by Redis)

**Creation**:
```bash
# Create private IP allocation
gcloud compute addresses create vhealth-private-ip-test \
  --global \
  --purpose=VPC_PEERING \
  --prefix-length=16 \
  --network=default

# Create service networking connection
gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=vhealth-private-ip-test \
  --network=default
```

**IMPORTANT**: Must import to Terraform state:
```bash
terraform import google_service_networking_connection.private_vpc_connection \
  vhealth-test:servicenetworking.googleapis.com:default
```

---

## IV. DATABASE INFRASTRUCTURE

### 4.1 Cloud SQL PostgreSQL
**Configuration** (test.tfvars):
```hcl
cloud_sql_instance_name       = "vhealth-backend-db-test"
cloud_sql_database_version    = "POSTGRES_15"
cloud_sql_tier                = "db-f1-micro"  # Smallest instance
cloud_sql_availability_type   = "ZONAL"        # Single zone for test
cloud_sql_backup_enabled      = true
cloud_sql_backup_start_time   = "20:00"        # 3 AM Vietnam time
cloud_sql_database_name       = "health_management"
cloud_sql_deletion_protection = false          # Allow deletion in test
```

**Key Differences from Prod**:
- Test: `db-f1-micro` (0.6GB RAM, shared vCPU) - $7.67/month
- Prod: `db-f1-micro` (same tier for cost optimization)
- Test: ZONAL (no HA) vs Prod: ZONAL (test doesn't need HA)

**IP Configuration**:
- Public IP: Enabled (Cloud Run connects via public IP)
- SSL Mode: `ENCRYPTED_ONLY` (required)
- Authorized Networks: `0.0.0.0/0` (allow from anywhere - simplified for test)

**Database User**:
- Username: `app_user`
- Password: Auto-generated 32-char random password (via Terraform)
- Stored in Secret Manager as `DATABASE_URL`

### 4.2 Database Migration Setup
**After Cloud SQL provisioned:**
```bash
# Get connection info from Terraform outputs
DB_HOST=$(terraform output -raw cloud_sql_public_ip)
DB_USER=$(terraform output -raw db_user)
DB_PASS=$(terraform output -raw db_password)

# Run Alembic migrations
cd scripts
DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:5432/health_management?sslmode=require" \
  alembic upgrade head
```

---

## V. CACHING INFRASTRUCTURE

### 5.1 Redis Memorystore
**Configuration** (test.tfvars):
```hcl
redis_tier           = "BASIC"         # No HA for test
redis_memory_size_gb = 1               # 1GB minimum
redis_version        = "REDIS_7_0"
enable_redis_cache   = true
redis_maintenance_day  = "SUNDAY"
redis_maintenance_hour = 3
```

**Key Settings**:
- Instance name: `vhealth-cache-test`
- Network: Connected to default VPC via private service connection
- Access: Via VPC connector from Cloud Run
- AUTH enabled: Password stored in Secret Manager

**Cost**: ~$35/month (BASIC tier, 1GB)

**Access Configuration**:
- Cloud Run service account needs access to Redis auth secret
- Configured via IAM binding in Terraform

---

## VI. STORAGE INFRASTRUCTURE

### 6.1 GCS Buckets

#### Models Bucket
**Purpose**: Store SBERT models, obesity prediction models, Q&A data

```bash
gsutil mb -p vhealth-test -l asia-southeast1 gs://vhealth-test-models

# Set lifecycle policy (auto-delete tmp files after 90 days)
cat > lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 90, "matchesPrefix": ["tmp/"]}
      }
    ]
  }
}
EOF

gsutil lifecycle set lifecycle.json gs://vhealth-test-models
```

**Upload Models**:
```bash
# Vietnamese SBERT model
gsutil -m cp -r models/vietnamese-sbert gs://vhealth-test-models/models/

# Q&A data files
gsutil -m cp data.xlsx gs://vhealth-test-models/data/
gsutil -m cp tuvung.txt gs://vhealth-test-models/data/
```

#### Public Bucket
**Purpose**: Store generated PDFs, user uploads

```bash
gsutil mb -p vhealth-test -l asia-southeast1 gs://vhealth-test-public

# Set public access for PDFs (optional - configure based on requirements)
gsutil iam ch allUsers:objectViewer gs://vhealth-test-public
```

**IAM**:
- Cloud Run SA: `roles/storage.objectAdmin` on both buckets

### 6.2 Artifact Registry
**Purpose**: Store Docker images (base + application)

```bash
gcloud artifacts repositories create vhealth-backend-test \
  --repository-format=docker \
  --location=asia-southeast1 \
  --description="Docker repository for VHealth backend - test environment"
```

**Registry URL**: `asia-southeast1-docker.pkg.dev/vhealth-test/vhealth-backend-test`

---

## VII. SECRET MANAGER CONFIGURATION

### 7.1 Required Secrets

**Database Secrets**:
```bash
# DATABASE_URL (auto-generated by Terraform from Cloud SQL outputs)
# Format: postgresql://app_user:PASSWORD@PUBLIC_IP:5432/health_management?sslmode=require
```

**Application Secrets**:
```bash
# Generate JWT secret
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')
echo -n "$SECRET_KEY" | gcloud secrets create vhealth-test-secret-key \
  --data-file=- --replication-policy=automatic

# Google OAuth (optional for test)
echo -n "PLACEHOLDER_CLIENT_ID" | gcloud secrets create vhealth-test-google-client-id \
  --data-file=- --replication-policy=automatic

echo -n "PLACEHOLDER_CLIENT_SECRET" | gcloud secrets create vhealth-test-google-client-secret \
  --data-file=- --replication-policy=automatic

# Email credentials
echo -n "congsynh.vo@gmail.com" | gcloud secrets create vhealth-test-mail-username \
  --data-file=- --replication-policy=automatic

echo -n "YOUR_APP_PASSWORD" | gcloud secrets create vhealth-test-mail-password \
  --data-file=- --replication-policy=automatic

echo -n "congsynh.vo@gmail.com" | gcloud secrets create vhealth-test-mail-from \
  --data-file=- --replication-policy=automatic

echo -n "smtp.gmail.com" | gcloud secrets create vhealth-test-mail-server \
  --data-file=- --replication-policy=automatic

# OpenAI API Key (CRITICAL for Q&A AI summarization)
echo -n "sk-proj-YOUR_OPENAI_KEY" | gcloud secrets create vhealth-test-openai-api-key \
  --data-file=- --replication-policy=automatic
```

**Redis Secrets** (auto-created by Terraform):
- `vhealth-test-redis-host`
- `vhealth-test-redis-port`
- `vhealth-test-redis-auth-secret`
- `vhealth-test-enable-redis-cache`

### 7.2 IAM Access
**Grant Cloud Run SA access**:
```bash
# Automatically handled by Terraform secret_manager module
# Manual verification:
gcloud secrets add-iam-policy-binding vhealth-test-openai-api-key \
  --member="serviceAccount:vhealth-backend-test@vhealth-test.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## VIII. TERRAFORM BACKEND SETUP

### 8.1 Create State Bucket
**Purpose**: Store Terraform state files

```bash
gsutil mb -p vhealth-test -l asia-southeast1 gs://vhealth-test-backend-tfstate

# Enable versioning
gsutil versioning set on gs://vhealth-test-backend-tfstate

# Set lifecycle to keep last 10 versions
cat > state-lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"numNewerVersions": 10}
      }
    ]
  }
}
EOF

gsutil lifecycle set state-lifecycle.json gs://vhealth-test-backend-tfstate
```

### 8.2 Backend Configuration
**In main.tf**:
```hcl
terraform {
  backend "gcs" {
    bucket = "vhealth-test-backend-tfstate"
    prefix = "terraform/state/test"
  }
}
```

**Initialize**:
```bash
cd terraform
terraform init \
  -backend-config="bucket=vhealth-test-backend-tfstate" \
  -backend-config="prefix=terraform/state/test" \
  -reconfigure
```

---

## IX. TERRAFORM ENVIRONMENT FILE

### 9.1 Create test.tfvars

**Create**: `terraform/environments/test.tfvars`

```hcl
# Project Configuration
project_id  = "vhealth-test"
region      = "asia-southeast1"
environment = "test"

# Artifact Registry
artifact_registry_repository_id = "vhealth-backend-test"

# VPC Connector
vpc_connector_name          = "vhealth-vpc-conn-test"
vpc_network                 = "default"
vpc_connector_ip_range      = "10.9.0.0/28"
vpc_connector_min_instances = 2
vpc_connector_max_instances = 3
vpc_connector_machine_type  = "e2-micro"

# Cloud SQL
cloud_sql_instance_name       = "vhealth-backend-db-test"
cloud_sql_database_version    = "POSTGRES_15"
cloud_sql_tier                = "db-f1-micro"
cloud_sql_availability_type   = "ZONAL"
cloud_sql_backup_enabled      = true
cloud_sql_backup_start_time   = "20:00"
cloud_sql_database_name       = "health_management"
cloud_sql_deletion_protection = false

# Cloud Run
cloud_run_service_name    = "vhealth-backend-test"
cloud_run_image           = "asia-southeast1-docker.pkg.dev/vhealth-test/vhealth-backend-test/health-api:latest"
cloud_run_cpu_limit       = "2000m"
cloud_run_memory_limit    = "2Gi"
cloud_run_max_instances   = 3
cloud_run_min_instances   = 0
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

# Domain Configuration (Optional - configure after Cloud Run deployment)
enable_custom_domain = false  # Set true after DNS configured
custom_domain        = "vhealth.io.vn"
api_subdomain        = "test.api"  # Creates test.api.vhealth.io.vn
enable_cdn           = false  # Can enable later

# Cloud Scheduler Configuration
scheduler_endpoint_url    = "https://test.api.vhealth.io.vn/api/v1/scheduler/hello-world"
scheduler_cron_schedule   = "*/30 * * * *"  # Every 30 minutes
scheduler_time_zone       = "Asia/Ho_Chi_Minh"
scheduler_use_oidc_auth   = false
scheduler_paused          = false

# Redis Configuration
redis_tier           = "BASIC"
redis_memory_size_gb = 1
enable_redis_cache   = true
```

### 9.2 Update Terraform Variables Validation

**Edit**: `terraform/variables.tf`

**Change validation** for environment variable:
```hcl
variable "environment" {
  description = "Environment name (dev, test, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "test", "prod"], var.environment)
    error_message = "Environment must be either 'dev', 'test', or 'prod'."
  }
}
```

---

## X. CI/CD PIPELINE CONFIGURATION

### 10.1 Jenkins Parameter Update

**Edit Jenkinsfile** - Update ENVIRONMENT parameter choices:
```groovy
parameters {
    choice(
        name: 'ENVIRONMENT',
        choices: ['test', 'prod'],  // Removed 'dev', added 'test'
        description: 'Target environment for deployment'
    )
    // ... other parameters
}
```

**Update environment logic**:
```groovy
environment {
    GCP_PROJECT_ID = "${params.ENVIRONMENT == 'prod' ? 'vhealth-prod' : 'vhealth-test'}"
    // ... rest of environment config
}
```

### 10.2 Jenkins Credentials

**Required credentials in Jenkins**:
1. `gcp-service-account-key` - Terraform SA key (JSON file)
2. Environment variables in Jenkins job or global config

### 10.3 First Deployment Workflow

**Step 1: Initial Terraform Apply** (Manual)
```bash
cd terraform

# Initialize
terraform init \
  -backend-config="bucket=vhealth-test-backend-tfstate" \
  -backend-config="prefix=terraform/state/test"

# Import VPC connection
terraform import -var-file="environments/test.tfvars" \
  google_service_networking_connection.private_vpc_connection \
  vhealth-test:servicenetworking.googleapis.com:default

# Plan
terraform plan -var-file="environments/test.tfvars" -out=tfplan

# Apply
terraform apply tfplan
```

**Step 2: Run Database Migrations**
```bash
cd scripts

# Get DB credentials from Terraform
DB_HOST=$(cd ../terraform && terraform output -raw cloud_sql_public_ip)
DB_USER=$(cd ../terraform && terraform output -raw db_user)
DB_PASS=$(cd ../terraform && terraform output -raw db_password)

# Run migrations
DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:5432/health_management?sslmode=require" \
  alembic upgrade head
```

**Step 3: Deploy via Jenkins**
- ENVIRONMENT: test
- BRANCH_NAME: develop (or feature branch)
- REBUILD_BASE_IMAGE: true (first deployment)

---

## XI. DOMAIN & DNS CONFIGURATION (Optional)

### 11.1 DNS Records
**If using custom domain** (test.api.vhealth.io.vn):

**After Cloud Run deployed**:
1. Get Cloud Run service URL from output
2. Create DNS records:
   - Type: CNAME
   - Name: test.api
   - Target: ghs.googlehosted.com
3. Verify domain ownership in GCP Console
4. Update test.tfvars: `enable_custom_domain = true`
5. Re-run Terraform

### 11.2 SSL Certificate
**Automatically provisioned** by Cloud Run domain mapping (can take 15-60 minutes)

---

## XII. COST ESTIMATION

### Monthly Cost Breakdown (Test Environment)

| Service | Configuration | Est. Cost/Month |
|---------|---------------|-----------------|
| Cloud SQL (db-f1-micro) | 0.6GB RAM, ZONAL, 10GB SSD | $7.67 |
| Redis Memorystore (BASIC) | 1GB, BASIC tier | $35.00 |
| VPC Connector | e2-micro, 2-3 instances | $12.00 |
| Cloud Run | 2Gi RAM, 2 vCPU, low traffic | $5-15 |
| Cloud Storage | 3 buckets, minimal data | $1-3 |
| Artifact Registry | Docker images | $0.50 |
| Secret Manager | ~15 secrets, low access | $0.30 |
| **TOTAL** | | **~$61-73/month** |

**Cost Optimization Options**:
1. **Disable Redis**: Set `enable_redis_cache = false` (saves $35/month)
   - Application works without cache - graceful fallback
2. **Manual VPC Connector**: Only create when Redis enabled
3. **Reduce Cloud Run resources**: 1Gi RAM / 1 vCPU (saves ~$5/month)

---

## XIII. VALIDATION CHECKLIST

### Pre-Deployment Validation
- [ ] Billing account linked to vhealth-test
- [ ] All required APIs enabled
- [ ] Service accounts created with proper IAM roles
- [ ] VPC connector IP range doesn't conflict (10.9.0.0/28)
- [ ] Private service connection established
- [ ] GCS buckets created (models, public, tfstate)
- [ ] Artifact Registry repository created
- [ ] All secrets created in Secret Manager
- [ ] OpenAI API key valid and working
- [ ] Models uploaded to GCS bucket
- [ ] test.tfvars file created with correct values
- [ ] Terraform backend configured
- [ ] VPC connection imported to Terraform state

### Post-Deployment Validation
- [ ] Terraform apply successful (all resources created)
- [ ] Cloud SQL instance running (check public IP)
- [ ] Redis instance provisioned (check host/port)
- [ ] Database migrations completed (alembic current)
- [ ] Docker base image built and pushed
- [ ] Docker app image built and pushed
- [ ] Cloud Run service deployed
- [ ] Service responds to health checks: `/health`
- [ ] Q&A health check passes: `/api/v1/qa/health`
- [ ] Cache health check passes: `/api/v1/cache/health`
- [ ] API docs accessible: `/docs`

### Integration Testing
```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe vhealth-backend-test \
  --region=asia-southeast1 \
  --project=vhealth-test \
  --format='value(status.url)')

# Test health
curl -f $SERVICE_URL/health

# Test Q&A health
curl -f $SERVICE_URL/api/v1/qa/health

# Test cache health
curl -f $SERVICE_URL/api/v1/cache/health

# Test root endpoint
curl -f $SERVICE_URL/

# View API docs
open $SERVICE_URL/docs
```

---

## XIV. CRITICAL GOTCHAS & WARNINGS

### 14.1 First-Time Setup Issues

**VPC Connection Import**:
- MUST manually import after creating private service connection
- Terraform will fail without this import
- Run BEFORE first `terraform apply`

**Artifact Registry Authentication**:
- Jenkins must authenticate: `gcloud auth configure-docker asia-southeast1-docker.pkg.dev`
- Service account needs `roles/artifactregistry.writer`

**Cloud SQL Public IP**:
- Takes 2-5 minutes to provision
- Cannot connect until SSL certificate ready
- Test connection before running migrations

**Redis Private IP**:
- Only accessible via VPC connector
- Cloud Run must have `--vpc-connector` configured
- Test Redis auth token in Secret Manager

### 14.2 Common Deployment Failures

**Model Download Timeout**:
- If GCS models not uploaded: startup fails or slow (downloads from HuggingFace)
- Upload models BEFORE first deployment
- Check: `gsutil ls gs://vhealth-test-models/models/vietnamese-sbert/`

**OpenAI API Key Missing**:
- Q&A service starts but AI summarization fails
- Check secret exists: `gcloud secrets describe vhealth-test-openai-api-key`
- Verify Cloud Run SA has secretAccessor role

**Database Connection Refused**:
- Check Cloud SQL authorized networks (should be 0.0.0.0/0)
- Verify DATABASE_URL secret format
- Ensure SSL mode: `?sslmode=require`

**Memory Issues**:
- Model loading requires ~1.5GB RAM
- Cloud Run needs 2Gi minimum for smooth startup
- Reduce to 1Gi if SBERT models not loaded

### 14.3 Security Considerations

**Test Environment - Lower Security**:
- SQL authorized networks: 0.0.0.0/0 (simplified)
- Deletion protection: false (allows teardown)
- Debug mode: enabled (more verbose logs)
- Public access: allowed (no authentication on Cloud Run)

**Before Production**:
- Review IP whitelisting
- Enable deletion protection
- Disable debug mode
- Consider Cloud Run authentication

---

## XV. MIGRATION FROM DEV TO TEST

### 15.1 Code Changes Required

**Update Environment References**:
```bash
# Find all "dev" references that should be "test"
grep -r "vhealth-dev" --exclude-dir=.git --exclude-dir=docs

# Update Jenkinsfile
sed -i '' 's/vhealth-dev/vhealth-test/g' Jenkinsfile

# Update any hardcoded dev references in code
grep -r "dev.vhealth" app/ --exclude-dir=__pycache__
```

**Database Migration Scripts**:
```bash
# Update connection strings in migration scripts if hardcoded
cd scripts/migrations
# Check .env files for dev references
```

### 15.2 Jenkins Job Configuration

**Create New Jenkins Job**:
- Name: "vhealth-test-deployment"
- Copy from: "vhealth-prod-deployment" (if exists)
- Update parameters: ENVIRONMENT choices = ['test', 'prod']
- Update GCP_PROJECT_ID logic

---

## XVI. NEXT STEPS & RECOMMENDATIONS

### Immediate Actions (Priority Order)

1. **Enable Billing** - Cannot proceed without this
2. **Enable APIs** - Required for all services
3. **Create Service Accounts** - Needed for Terraform automation
4. **Setup Terraform Backend** - State storage
5. **Create test.tfvars** - Environment configuration
6. **Establish VPC Connection** - Required for Redis
7. **Create GCS Buckets** - Upload models before deployment
8. **Upload Models to GCS** - Prevent startup delays
9. **Create Secrets** - Including critical OpenAI API key
10. **Run Terraform Apply** - Provision infrastructure
11. **Run Database Migrations** - Initialize schema
12. **Deploy via Jenkins** - First application deployment

### Optional Enhancements

**Cost Optimization**:
- Start without Redis (save $35/month)
- Add Redis later when testing cache functionality
- Use Cloud Run min_instances = 0 (cold starts acceptable for test)

**Monitoring Setup**:
- Enable Cloud Logging (included in free tier)
- Setup basic alerting for service downtime
- Configure uptime checks for /health endpoint

**CI/CD Improvements**:
- Separate Jenkins job for test environment
- Add smoke tests specific to test environment
- Configure automatic deployments on develop branch commits

---

## XVII. QUESTIONS & CLARIFICATIONS

### Architecture Decisions

**Q1: Do we need Redis in test environment?**
- **Recommendation**: START WITHOUT (save $35/month)
- App gracefully handles missing cache
- Add later when testing cache-specific features
- **Action**: Set `enable_redis_cache = false` initially

**Q2: Custom domain for test environment?**
- **Recommendation**: SKIP INITIALLY
- Use Cloud Run default URL first: `*.run.app`
- Add custom domain after validating deployment
- **Action**: Set `enable_custom_domain = false`

**Q3: Cloud SQL tier for test?**
- **Current**: db-f1-micro (same as prod)
- **Recommendation**: KEEP db-f1-micro ($7.67/month - cheapest)
- Alternative: db-g1-small ($25/month) if performance issues
- **Action**: Start with db-f1-micro

**Q4: Should we replicate Cloud Scheduler?**
- **Current Prod**: 30-minute cron job for /scheduler/hello-world
- **Recommendation**: SKIP INITIALLY (not critical for test)
- Can add later via Terraform when needed
- **Action**: Comment out scheduler module in main.tf for test

### Operational Questions

**Q5: How to handle model files?**
- **Option A**: Upload to GCS bucket (recommended)
  - Faster startup
  - Consistent with prod
  - One-time upload
- **Option B**: Download from HuggingFace
  - No upload needed
  - Slower first startup (5-10 minutes)
  - Auto-fallback if GCS fails
- **Recommendation**: Use Option A

**Q6: Who manages secrets rotation?**
- **Test Environment**: Manual rotation acceptable
- **Production**: Consider Secret Manager auto-rotation
- **Action**: Document secret update procedure

**Q7: Backup strategy for test?**
- **Current**: 7-day retention (same as prod)
- **Recommendation**: Acceptable for test
- Can reduce to 1-day if cost sensitive
- **Action**: Keep 7-day retention

---

## XVIII. CONTACT & SUPPORT

**GCP Account Owner**: oryndrvn@gmail.com
**Project ID**: vhealth-test
**Region**: asia-southeast1

**Key Resources**:
- Terraform Docs: `/terraform/`
- CLAUDE.md: Project documentation
- Migration Scripts: `/scripts/migrations/`

**Troubleshooting**:
- GCP Console: https://console.cloud.google.com/
- Cloud Run Logs: `gcloud run logs tail vhealth-backend-test`
- Cloud SQL Logs: GCP Console → SQL → Logs

---

## APPENDIX A: Quick Start Commands

**Complete Initial Setup** (run in order):
```bash
# 1. Set project
gcloud config set project vhealth-test
gcloud config set compute/region asia-southeast1

# 2. Enable APIs
gcloud services enable run.googleapis.com sqladmin.googleapis.com \
  secretmanager.googleapis.com artifactregistry.googleapis.com \
  storage.googleapis.com redis.googleapis.com compute.googleapis.com \
  vpcaccess.googleapis.com servicenetworking.googleapis.com

# 3. Create service accounts
gcloud iam service-accounts create vhealth-backend-test \
  --display-name="Cloud Run SA - test"

gcloud iam service-accounts create vhealth-terraform \
  --display-name="Terraform Automation SA"

# 4. Create state bucket
gsutil mb -p vhealth-test -l asia-southeast1 gs://vhealth-test-backend-tfstate
gsutil versioning set on gs://vhealth-test-backend-tfstate

# 5. Create private IP allocation
gcloud compute addresses create vhealth-private-ip-test \
  --global --purpose=VPC_PEERING --prefix-length=16 --network=default

gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=vhealth-private-ip-test \
  --network=default

# 6. Create GCS buckets
gsutil mb -p vhealth-test -l asia-southeast1 gs://vhealth-test-models
gsutil mb -p vhealth-test -l asia-southeast1 gs://vhealth-test-public

# 7. Create Artifact Registry
gcloud artifacts repositories create vhealth-backend-test \
  --repository-format=docker \
  --location=asia-southeast1

# 8. Initialize Terraform
cd terraform
terraform init \
  -backend-config="bucket=vhealth-test-backend-tfstate" \
  -backend-config="prefix=terraform/state/test"

# 9. Import VPC connection
terraform import -var-file="environments/test.tfvars" \
  google_service_networking_connection.private_vpc_connection \
  vhealth-test:servicenetworking.googleapis.com:default

# 10. Apply Terraform
terraform plan -var-file="environments/test.tfvars" -out=tfplan
terraform apply tfplan

# 11. Run migrations
cd ../scripts
DB_HOST=$(cd ../terraform && terraform output -raw cloud_sql_public_ip)
DB_USER=$(cd ../terraform && terraform output -raw db_user)
DB_PASS=$(cd ../terraform && terraform output -raw db_password)

DATABASE_URL="postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:5432/health_management?sslmode=require" \
  alembic upgrade head
```

---

## APPENDIX B: Cost Optimization Scenarios

### Scenario 1: Minimal Test Environment
**Configuration**:
- No Redis (disable cache)
- Cloud Run: 0 min instances, 1Gi RAM
- Cloud SQL: db-f1-micro
- Storage: Minimal

**Monthly Cost**: ~$15-20
- Cloud SQL: $7.67
- Cloud Run: $5-8 (pay per use)
- Storage: $1-3
- No VPC Connector needed (no Redis)

### Scenario 2: Full-Featured Test
**Configuration** (Recommended):
- Redis enabled (1GB BASIC)
- Cloud Run: 0 min instances, 2Gi RAM
- Cloud SQL: db-f1-micro
- VPC Connector: e2-micro

**Monthly Cost**: ~$61-73
- Full parity with production architecture
- Cache testing enabled
- Better performance

### Scenario 3: Performance Test
**Configuration**:
- Redis: STANDARD_HA (3GB)
- Cloud Run: 1 min instance, 4Gi RAM
- Cloud SQL: db-g1-small
- VPC Connector: e2-small

**Monthly Cost**: ~$150-180
- For load testing
- Not recommended for regular test environment

---

**Document Version**: 1.0
**Last Updated**: 2025-11-28
**Status**: Ready for Implementation
