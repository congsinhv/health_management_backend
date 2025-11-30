# Deployment Guide

**VHealth Backend - Comprehensive Deployment Instructions**

Last Updated: 2025-11-25
Version: 1.0.0

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Environment Configuration](#3-environment-configuration)
4. [Docker Build Process](#4-docker-build-process)
5. [Jenkins Pipeline Deployment](#5-jenkins-pipeline-deployment)
6. [Manual Deployment](#6-manual-deployment)
7. [Database Migrations](#7-database-migrations)
8. [Post-Deployment Verification](#8-post-deployment-verification)
9. [Rollback Procedures](#9-rollback-procedures)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Overview

### Deployment Architecture

VHealth Backend is deployed on **Google Cloud Run** using a containerized approach with the following components:

- **Application**: FastAPI on Cloud Run
- **Database**: Cloud SQL for PostgreSQL
- **Cache**: Memorystore for Redis
- **Storage**: Google Cloud Storage (models, PDFs)
- **Secrets**: Secret Manager
- **Container Registry**: Artifact Registry
- **Infrastructure**: Terraform-managed

### Deployment Environments

| Environment | Branch | Domain | Purpose |
|-------------|--------|--------|---------|
| **Development** | `develop` | dev.vhealth.example.com | Testing and development |
| **Production** | `main` | api.vhealth.example.com | Production traffic |

---

## 2. Prerequisites

### Required Access

- **Google Cloud Platform**:
  - Project access (`vhealth-dev` or `vhealth-prod`)
  - Cloud Run Admin
  - Cloud SQL Admin
  - Storage Admin
  - Artifact Registry Writer
  - Secret Manager Secret Accessor

- **Jenkins**:
  - Access to Jenkins server
  - Permission to trigger builds

- **Git**:
  - Access to repository
  - Push access to `develop` and `main` branches

### Required Tools

```bash
# Google Cloud SDK
gcloud --version  # >= 450.0.0

# Docker
docker --version  # >= 24.0.0

# Terraform
terraform --version  # >= 1.6.0

# Python
python --version  # >= 3.13

# PostgreSQL client (for migrations)
psql --version  # >= 15.0
```

### Required Credentials

- **GCP Service Account**:
  - Stored in Jenkins credentials
  - Access to all required services

- **API Keys**:
  - OpenAI API key (for AI features)
  - Google OAuth credentials (for social login)
  - SMTP credentials (for email)

---

## 3. Environment Configuration

### Environment Variables

Create `.env` file for local development or configure in Secret Manager for production:

```bash
# Application
APP_NAME=Health Management API
DEBUG=false                    # true for dev, false for prod
LOG_LEVEL=INFO                 # DEBUG for dev, INFO for prod
ENVIRONMENT=production         # development, production

# Database
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/db
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10

# Security
SECRET_KEY=<strong-random-key>  # Generate with: openssl rand -hex 32
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
ALGORITHM=HS256

# Q&A Service
QA_ENABLED=true
QA_MODEL_PATH=/app/.cache/models/vietnamese-sbert
QA_DATA_PATH=/app/.cache/data/data.xlsx
QA_VOCAB_PATH=/app/.cache/data/tuvung.txt
QA_THRESHOLD=0.55
QA_TOP_K=7
QA_MAX_RESULTS_PER_FIELD=5

# OpenAI
OPENAI_API_KEY=<your-api-key>
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT=30
OPENAI_TEMPERATURE=0.5
OPENAI_MAX_TOKENS=400

# Google Cloud
GCP_PROJECT_ID=vhealth-prod
GCP_MODEL_BUCKET=vhealth-prod-models
GCP_PUBLIC_BUCKET=vhealth-prod-public
MODEL_AUTO_DOWNLOAD=true

# OAuth (Optional)
GOOGLE_CLIENT_ID=<your-client-id>
GOOGLE_CLIENT_SECRET=<your-client-secret>
GOOGLE_REDIRECT_URI=https://api.vhealth.example.com/api/v1/auth/google/callback

# Email (Optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=<app-password>
MAIL_FROM=noreply@vhealth.example.com

# Redis Cache
ENABLE_REDIS_CACHE=true
REDIS_URL=redis://10.0.0.3:6379/0  # Memorystore private IP
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5

# CORS
CORS_ORIGINS=["https://app.vhealth.example.com","https://www.vhealth.example.com"]

# Performance
OBESITY_MODEL_DIR=/app/.cache/models_obesity
```

### Secret Manager Configuration

Store sensitive values in Secret Manager:

```bash
# Create secrets
gcloud secrets create openai-api-key \
  --data-file=- <<< "$OPENAI_API_KEY" \
  --project=vhealth-prod

gcloud secrets create database-url \
  --data-file=- <<< "$DATABASE_URL" \
  --project=vhealth-prod

gcloud secrets create secret-key \
  --data-file=- <<< "$SECRET_KEY" \
  --project=vhealth-prod

# Grant access to Cloud Run service account
gcloud secrets add-iam-policy-binding openai-api-key \
  --member="serviceAccount:vhealth-prod@vhealth-prod.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 4. Docker Build Process

### CRITICAL: Vietnamese Font Requirements

**Both Docker images MUST include Vietnamese font support for PDF generation:**

#### Dockerfile (Application Image)

```dockerfile
# Lines 17-18: Vietnamese fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    fonts-dejavu-core \      # Required for Vietnamese text
    fonts-noto-core \        # Required for Vietnamese text
    && rm -rf /var/lib/apt/lists/*
```

#### Dockerfile.base (Base Image)

```dockerfile
# Lines 44-54: Vietnamese fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    fonts-dejavu-core \      # Required for Vietnamese text
    fonts-noto-core \        # Required for Vietnamese text
    && rm -rf /var/lib/apt/lists/*
```

**Why This Matters:**
- Without these fonts, PDFs render with blank rectangles instead of Vietnamese characters
- This issue only appears in containerized/production environments
- Font missing errors may not appear in logs (silent failure)

### Building Base Image

**When to rebuild:**
- Changes to `requirements-prod.txt`
- Changes to `Dockerfile.base`
- Changes to system dependencies
- Python version update

```bash
# Build base image locally
docker build -f Dockerfile.base -t vhealth-base:latest .

# Tag for Artifact Registry
docker tag vhealth-base:latest \
  asia-southeast1-docker.pkg.dev/vhealth-prod/vhealth/base:latest

# Push to registry
docker push asia-southeast1-docker.pkg.dev/vhealth-prod/vhealth/base:latest
```

**Jenkins approach:**
- Set `REBUILD_BASE_IMAGE=true` in pipeline parameters
- Base image is automatically rebuilt and pushed

### Building Application Image

```bash
# Build with base image
docker build \
  --build-arg BASE_IMAGE=asia-southeast1-docker.pkg.dev/vhealth-prod/vhealth/base:latest \
  -t vhealth-app:latest .

# Build standalone (without base image)
docker build -t vhealth-app:latest .

# Tag for Artifact Registry
docker tag vhealth-app:latest \
  asia-southeast1-docker.pkg.dev/vhealth-prod/vhealth/app:$BUILD_NUMBER

# Push to registry
docker push asia-southeast1-docker.pkg.dev/vhealth-prod/vhealth/app:$BUILD_NUMBER
```

### Testing Docker Image Locally

```bash
# Run container locally
docker run -p 8080:8080 \
  --env-file .env \
  vhealth-app:latest

# Test health endpoint
curl http://localhost:8080/health

# Test PDF generation (verify fonts)
curl -X POST http://localhost:8080/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d @test-prediction.json

# Check PDF rendering
curl http://localhost:8080/api/v1/predict/$PREDICTION_ID/pdf \
  -H "Authorization: Bearer $TOKEN"
```

---

## 5. Jenkins Pipeline Deployment

### Pipeline Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ENVIRONMENT` | Choice | `dev` | Environment to deploy (dev, prod) |
| `BRANCH_NAME` | String | `develop` | Git branch to deploy |
| `REBUILD_BASE_IMAGE` | Boolean | `false` | Rebuild Dockerfile.base |
| `SKIP_TESTS` | Boolean | `false` | Skip running tests |
| `DRY_RUN` | Boolean | `false` | Terraform plan only |

### Deployment Steps

#### Step 1: Trigger Deployment

1. Go to Jenkins: https://jenkins.example.com
2. Select job: `vhealth-backend-deploy`
3. Click "Build with Parameters"
4. Configure parameters:
   - **ENVIRONMENT**: `prod`
   - **BRANCH_NAME**: `main`
   - **REBUILD_BASE_IMAGE**: `true` (if dependencies changed)
   - **SKIP_TESTS**: `false`
   - **DRY_RUN**: `false`
5. Click "Build"

#### Step 2: Monitor Pipeline

Pipeline stages:
1. ✅ **Checkout**: Clone repository
2. ✅ **Terraform Init**: Initialize infrastructure
3. ✅ **Terraform Plan**: Plan infrastructure changes
4. ⏸️ **Approval** (prod only): Manual approval required
5. ✅ **Build Base Image** (if REBUILD_BASE_IMAGE=true)
6. ✅ **Build App Image**: Build Docker image
7. ✅ **Run Tests** (if SKIP_TESTS=false)
8. ✅ **Push Image**: Push to Artifact Registry
9. ✅ **Terraform Apply**: Deploy infrastructure
10. ✅ **Deploy to Cloud Run**: Update service
11. ✅ **Smoke Tests**: Verify deployment
12. ✅ **Cleanup**: Remove old images

#### Step 3: Approval (Production Only)

For production deployments:
1. Pipeline pauses at "Approval" stage
2. Review Terraform plan output
3. Verify changes are expected
4. Click "Proceed" to continue or "Abort" to cancel

#### Step 4: Post-Deployment

After successful deployment:
1. Verify health check: `https://api.vhealth.example.com/health`
2. Check logs in Cloud Logging
3. Monitor error rates
4. Run smoke tests manually if needed

---

## 6. Manual Deployment

### Using Terraform

#### Step 1: Initialize Terraform

```bash
cd terraform
terraform init
```

#### Step 2: Plan Changes

```bash
# Development
terraform plan -var-file=environments/dev/terraform.tfvars

# Production
terraform plan -var-file=environments/prod/terraform.tfvars
```

#### Step 3: Apply Changes

```bash
# Development
terraform apply -var-file=environments/dev/terraform.tfvars

# Production (with approval)
terraform apply -var-file=environments/prod/terraform.tfvars
```

### Using gcloud CLI

#### Deploy to Cloud Run

```bash
# Set project
gcloud config set project vhealth-prod

# Deploy service
gcloud run deploy vhealth-backend-prod \
  --image=asia-southeast1-docker.pkg.dev/vhealth-prod/vhealth/app:BUILD_123 \
  --platform=managed \
  --region=asia-southeast1 \
  --allow-unauthenticated \
  --set-env-vars="$(cat .env.prod | grep -v '^#' | xargs | tr ' ' ',')" \
  --set-secrets="OPENAI_API_KEY=openai-api-key:latest,DATABASE_URL=database-url:latest" \
  --vpc-connector=vhealth-vpc-connector \
  --memory=2Gi \
  --cpu=1 \
  --min-instances=2 \
  --max-instances=100 \
  --concurrency=80 \
  --timeout=300

# Update traffic to new revision
gcloud run services update-traffic vhealth-backend-prod \
  --to-latest \
  --region=asia-southeast1
```

---

## 7. Database Migrations

### Running Migrations

#### Via Jenkins

Separate Jenkins job: `vhealth-backend-migrate`

Parameters:
- **ENVIRONMENT**: `dev` or `prod`
- **MIGRATION_DIRECTION**: `upgrade` or `downgrade`
- **TARGET_REVISION**: `head` or specific revision

#### Manual Migration

```bash
# Connect to Cloud SQL proxy
cloud_sql_proxy -instances=vhealth-prod:asia-southeast1:vhealth-db=tcp:5432 &

# Set database URL
export DATABASE_URL="postgresql://user:password@localhost:5432/vhealth"

# Navigate to migrations directory
cd scripts

# Check current version
alembic current

# View migration history
alembic history

# Upgrade to latest
alembic upgrade head

# Upgrade to specific revision
alembic upgrade abc123def456

# Downgrade one version
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade abc123def456
```

### Creating New Migrations

```bash
cd scripts

# Auto-generate migration
alembic revision --autogenerate -m "Add user_preferences table"

# Create empty migration (for data migrations)
alembic revision -m "Migrate user data"

# Edit generated migration file
vim migrations/versions/abc123def456_add_user_preferences_table.py

# Test migration
alembic upgrade head

# Test rollback
alembic downgrade -1
```

### Migration Best Practices

1. **Always test migrations locally first**
2. **Backup database before production migrations**
3. **Use transactions for data migrations**
4. **Make migrations reversible (downgrade)**
5. **Document complex migrations**
6. **Run migrations during low-traffic periods**

---

## 8. Post-Deployment Verification

### Health Checks

```bash
# Application health
curl https://api.vhealth.example.com/health

# Expected response:
{
  "status": "healthy",
  "database": "connected",
  "cache": "connected",
  "qa_service": "ready",
  "websocket_manager": "active"
}
```

### Endpoint Tests

```bash
# Q&A health
curl https://api.vhealth.example.com/api/v1/qa/health

# Cache health
curl https://api.vhealth.example.com/api/v1/cache/health

# Database statistics
curl https://api.vhealth.example.com/api/v1/performance/database
```

### Functional Tests

```bash
# 1. User registration
curl -X POST https://api.vhealth.example.com/api/v1/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123456",
    "full_name": "Test User"
  }'

# 2. User login
TOKEN=$(curl -X POST https://api.vhealth.example.com/api/v1/users/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123456"
  }' | jq -r '.access_token')

# 3. Ask Q&A question
curl -X POST https://api.vhealth.example.com/api/v1/qa/ask \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "question": "BMI là gì?"
  }'

# 4. Create prediction
PREDICTION_ID=$(curl -X POST https://api.vhealth.example.com/api/v1/predict \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d @test-prediction.json | jq -r '.id')

# 5. Generate PDF
curl -X POST https://api.vhealth.example.com/api/v1/predict/$PREDICTION_ID/pdf \
  -H "Authorization: Bearer $TOKEN"

# 6. Download PDF to verify fonts
curl -o test-report.pdf "$(curl -X POST \
  https://api.vhealth.example.com/api/v1/predict/$PREDICTION_ID/pdf \
  -H "Authorization: Bearer $TOKEN" | jq -r '.pdf_url')"

# Open PDF and verify Vietnamese text renders correctly
```

### Performance Verification

```bash
# Check response times
for i in {1..10}; do
  time curl -s https://api.vhealth.example.com/health > /dev/null
done

# Check cache hit rate
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://api.vhealth.example.com/api/v1/cache/stats

# Check database pool
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://api.vhealth.example.com/api/v1/performance/database
```

### Log Verification

```bash
# View Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=vhealth-backend-prod" \
  --limit=50 \
  --format=json \
  --project=vhealth-prod

# Filter for errors
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=vhealth-backend-prod AND severity>=ERROR" \
  --limit=50 \
  --format=json \
  --project=vhealth-prod
```

---

## 9. Rollback Procedures

### Automatic Rollback

Jenkins pipeline automatically rolls back if smoke tests fail.

### Manual Rollback

#### Option 1: Revert to Previous Revision

```bash
# List revisions
gcloud run revisions list \
  --service=vhealth-backend-prod \
  --region=asia-southeast1 \
  --project=vhealth-prod

# Route traffic to previous revision
gcloud run services update-traffic vhealth-backend-prod \
  --to-revisions=vhealth-backend-prod-00042-abc=100 \
  --region=asia-southeast1 \
  --project=vhealth-prod
```

#### Option 2: Deploy Previous Image

```bash
# Redeploy previous image
gcloud run deploy vhealth-backend-prod \
  --image=asia-southeast1-docker.pkg.dev/vhealth-prod/vhealth/app:122 \
  --region=asia-southeast1 \
  --project=vhealth-prod
```

#### Option 3: Terraform Rollback

```bash
# Revert Terraform state
cd terraform
git checkout main~1  # Previous commit
terraform apply -var-file=environments/prod/terraform.tfvars
```

### Database Rollback

```bash
# Connect to database
cloud_sql_proxy -instances=vhealth-prod:asia-southeast1:vhealth-db=tcp:5432 &

# Rollback migration
cd scripts
alembic downgrade -1

# Or rollback to specific version
alembic downgrade abc123def456
```

---

## 10. Troubleshooting

### Common Issues

#### Issue 1: PDF Rendering Fails (Vietnamese Characters Missing)

**Symptoms:**
- PDFs show blank rectangles instead of Vietnamese text
- No errors in logs

**Cause:**
- Missing Vietnamese fonts in Docker image

**Solution:**
```bash
# Verify fonts in Docker image
docker run --rm vhealth-app:latest fc-list | grep -i "dejavu\|noto"

# If fonts missing, rebuild with fonts
# Ensure Dockerfile contains:
RUN apt-get install -y fonts-dejavu-core fonts-noto-core

# Rebuild base image
REBUILD_BASE_IMAGE=true in Jenkins
```

#### Issue 2: Database Connection Timeout

**Symptoms:**
- Health check fails with database connection error
- Logs show `asyncpg.exceptions.ConnectionDoesNotExistError`

**Cause:**
- VPC connector misconfigured
- Cloud SQL instance not accessible

**Solution:**
```bash
# Check VPC connector
gcloud compute networks vpc-access connectors describe vhealth-vpc-connector \
  --region=asia-southeast1 \
  --project=vhealth-prod

# Check Cloud SQL instance
gcloud sql instances describe vhealth-db \
  --project=vhealth-prod

# Verify authorized networks
gcloud sql instances patch vhealth-db \
  --authorized-networks=CLOUD_RUN_CIDR \
  --project=vhealth-prod
```

#### Issue 3: Cache Connection Fails

**Symptoms:**
- Cache health check fails
- Application works but slower

**Cause:**
- Redis instance down or misconfigured
- VPC networking issue

**Solution:**
```bash
# Check Memorystore instance
gcloud redis instances describe vhealth-redis \
  --region=asia-southeast1 \
  --project=vhealth-prod

# Test Redis connection from Cloud Shell
gcloud compute ssh redis-test-vm --zone=asia-southeast1-a
redis-cli -h REDIS_PRIVATE_IP ping
```

#### Issue 4: Q&A Service Not Available

**Symptoms:**
- `/api/v1/qa/health` returns 503
- Logs show model loading timeout

**Cause:**
- Model files missing from GCS
- Auto-download failed

**Solution:**
```bash
# Check model files in GCS
gsutil ls gs://vhealth-prod-models/vietnamese-sbert/

# Manually download models
gsutil -m cp -r gs://vhealth-prod-models/vietnamese-sbert /tmp/

# Upload if missing
gsutil -m cp -r /path/to/local/model gs://vhealth-prod-models/vietnamese-sbert/

# Restart Cloud Run service
gcloud run services update vhealth-backend-prod \
  --region=asia-southeast1 \
  --project=vhealth-prod
```

#### Issue 5: High Memory Usage

**Symptoms:**
- Cloud Run instances crashing
- OOMKilled errors in logs

**Cause:**
- Memory leak
- SBERT model too large for container
- Too many concurrent requests

**Solution:**
```bash
# Increase memory allocation
gcloud run services update vhealth-backend-prod \
  --memory=4Gi \
  --region=asia-southeast1 \
  --project=vhealth-prod

# Reduce max instances temporarily
gcloud run services update vhealth-backend-prod \
  --max-instances=50 \
  --region=asia-southeast1 \
  --project=vhealth-prod

# Monitor memory usage
gcloud monitoring time-series list \
  --filter='resource.type="cloud_run_revision" AND metric.type="run.googleapis.com/container/memory/utilizations"' \
  --project=vhealth-prod
```

### Debugging Commands

```bash
# View real-time logs
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=vhealth-backend-prod" \
  --project=vhealth-prod

# Check environment variables
gcloud run services describe vhealth-backend-prod \
  --region=asia-southeast1 \
  --format="value(spec.template.spec.containers[0].env)" \
  --project=vhealth-prod

# Check service account permissions
gcloud projects get-iam-policy vhealth-prod \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:vhealth-prod@vhealth-prod.iam.gserviceaccount.com"

# Test from Cloud Shell
gcloud run services proxy vhealth-backend-prod \
  --region=asia-southeast1 \
  --port=8080 \
  --project=vhealth-prod

curl http://localhost:8080/health
```

### Getting Help

1. **Check Documentation**:
   - [CLAUDE.md](../CLAUDE.md)
   - [System Architecture](./system-architecture.md)
   - [Code Standards](./code-standards.md)

2. **Review Logs**:
   - Cloud Logging
   - Jenkins build logs
   - Application logs

3. **Contact Team**:
   - DevOps team for infrastructure issues
   - Backend team for application issues
   - DBA for database issues

---

## Related Documentation

- [CLAUDE.md](../CLAUDE.md) - Claude Code development guide
- [Project Overview & PDR](./project-overview-pdr.md) - Vision and requirements
- [System Architecture](./system-architecture.md) - Architecture diagrams
- [Code Standards](./code-standards.md) - Coding conventions
- [Project Roadmap](./project-roadmap.md) - Development roadmap
- [Codebase Summary](./codebase-summary.md) - Directory structure

---

## Changelog

### 2025-11-25
- Initial deployment guide creation
- Added Vietnamese font requirements (CRITICAL)
- Documented Docker build process
- Added Jenkins pipeline instructions
- Included troubleshooting section
- Added rollback procedures

---

**Note:** Keep this guide updated as deployment procedures change. Last review: 2025-11-25
