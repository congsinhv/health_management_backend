# Pre-Deployment Checklist

Complete this checklist before deploying to **Dev** or **Prod** environments.

## Environment Configuration

| Item | Dev | Prod |
|------|-----|------|
| GCP Project | `vhealth-dev` | `vhealth-prod` |
| Region | `asia-southeast1` | `asia-southeast1` |
| Model Bucket | `vhealth-dev-models` | `vhealth-prod-models` |
| Artifact Registry | `vhealth-backend-dev` | `vhealth-backend-prod` |
| Cloud Run Service | `vhealth-backend-dev` | `vhealth-backend-prod` |

---

## 1. ✅ GCS Model Buckets

### Check if buckets exist:
```bash
# Run the setup script
./scripts/setup_gcs_buckets.sh

# Or manually check
gsutil ls gs://vhealth-dev-models/
gsutil ls gs://vhealth-prod-models/
```

### Create buckets if needed:
```bash
# Dev
gsutil mb -p vhealth-dev -c STANDARD -l asia-southeast1 gs://vhealth-dev-models
gsutil versioning set on gs://vhealth-dev-models

# Prod
gsutil mb -p vhealth-prod -c STANDARD -l asia-southeast1 gs://vhealth-prod-models
gsutil versioning set on gs://vhealth-prod-models
```

### Set IAM permissions:
```bash
# Dev
gsutil iam ch serviceAccount:vhealth-backend-dev@vhealth-dev.iam.gserviceaccount.com:objectViewer gs://vhealth-dev-models

# Prod
gsutil iam ch serviceAccount:vhealth-backend-prod@vhealth-prod.iam.gserviceaccount.com:objectViewer gs://vhealth-prod-models
```

**Status:** [ ] Dev  [ ] Prod

---

## 2. ✅ Upload Model Files

### Option A: Use the upload script
```bash
./scripts/upload_models_to_gcs.sh
```

### Option B: Manual upload
```bash
# Dev
gsutil -m cp -r models/vietnamese-sbert/* gs://vhealth-dev-models/models/vietnamese-sbert/

# Prod
gsutil -m cp -r models/vietnamese-sbert/* gs://vhealth-prod-models/models/vietnamese-sbert/
```

### Verify upload:
```bash
# Dev
gsutil ls -r gs://vhealth-dev-models/models/vietnamese-sbert/

# Prod
gsutil ls -r gs://vhealth-prod-models/models/vietnamese-sbert/
```

**Expected files:**
- `config.json`
- `pytorch_model.bin` or `model.safetensors`
- `tokenizer_config.json`
- `vocab.txt`
- `special_tokens_map.json`
- `1_Pooling/config.json`
- Other model files

**Status:** [ ] Dev  [ ] Prod

---

## 3. ✅ Secret Manager Secrets

### Run the setup script:
```bash
./scripts/setup_secrets.sh
```

### Required secrets:

#### Dev Environment (`vhealth-dev` project):
- [ ] `vhealth-dev-database-url` - PostgreSQL connection string
  - Format: `postgresql://user:password@/cloudsql/vhealth-dev:asia-southeast1:vhealth-backend-db-dev/health_management`
- [ ] `vhealth-dev-secret-key` - JWT secret key (generate random 32+ chars)
- [ ] `vhealth-dev-google-client-id` - Google OAuth client ID
- [ ] `vhealth-dev-google-client-secret` - Google OAuth client secret
- [ ] `vhealth-dev-mail-username` - SMTP email address
- [ ] `vhealth-dev-mail-password` - SMTP email password (app-specific password)

#### Prod Environment (`vhealth-prod` project):
- [ ] `vhealth-prod-database-url` - PostgreSQL connection string
  - Format: `postgresql://user:password@/cloudsql/vhealth-prod:asia-southeast1:vhealth-backend-db-prod/health_management`
- [ ] `vhealth-prod-secret-key` - JWT secret key (different from dev!)
- [ ] `vhealth-prod-google-client-id` - Google OAuth client ID
- [ ] `vhealth-prod-google-client-secret` - Google OAuth client secret
- [ ] `vhealth-prod-mail-username` - SMTP email address
- [ ] `vhealth-prod-mail-password` - SMTP email password

### Verify secrets:
```bash
# Dev
gcloud secrets list --project=vhealth-dev --filter="name:vhealth-dev"

# Prod
gcloud secrets list --project=vhealth-prod --filter="name:vhealth-prod"
```

### Verify IAM permissions:
```bash
# Dev - Cloud Run SA should have secretAccessor role
gcloud secrets get-iam-policy vhealth-dev-database-url --project=vhealth-dev

# Prod
gcloud secrets get-iam-policy vhealth-prod-database-url --project=vhealth-prod
```

**Status:** [ ] Dev secrets created  [ ] Prod secrets created

---

## 4. ✅ Cloud SQL Database

### Verify database instances exist:
```bash
# Dev
gcloud sql instances describe vhealth-backend-db-dev --project=vhealth-dev

# Prod
gcloud sql instances describe vhealth-backend-db-prod --project=vhealth-prod
```

### Verify database exists:
```bash
# Dev
gcloud sql databases list --instance=vhealth-backend-db-dev --project=vhealth-dev | grep health_management

# Prod
gcloud sql databases list --instance=vhealth-backend-db-prod --project=vhealth-prod | grep health_management
```

### Run database migrations (if needed):
```bash
# This will be done automatically by Cloud Run on first deployment
# Or you can run manually:
# cd /path/to/project
# export DATABASE_URL="postgresql://..."
# alembic upgrade head
```

**Status:** [ ] Dev database ready  [ ] Prod database ready

---

## 5. ✅ Artifact Registry

### Verify repositories exist:
```bash
# Dev
gcloud artifacts repositories describe vhealth-backend-dev \
    --location=asia-southeast1 \
    --project=vhealth-dev

# Prod
gcloud artifacts repositories describe vhealth-backend-prod \
    --location=asia-southeast1 \
    --project=vhealth-prod
```

### Create if needed:
```bash
# Dev
gcloud artifacts repositories create vhealth-backend-dev \
    --repository-format=docker \
    --location=asia-southeast1 \
    --project=vhealth-dev

# Prod
gcloud artifacts repositories create vhealth-backend-prod \
    --repository-format=docker \
    --location=asia-southeast1 \
    --project=vhealth-prod
```

**Status:** [ ] Dev  [ ] Prod

---

## 6. ✅ Jenkins Configuration

### Run verification script:
```bash
./scripts/verify_jenkins_setup.sh
```

### Manual checks:

#### Jenkins Credentials:
- [ ] GCP service account key uploaded as `gcp-service-account-key`
- [ ] Service account has required roles (see script)

#### Required Jenkins Plugins:
- [ ] Pipeline
- [ ] Git
- [ ] Credentials Binding
- [ ] Docker Pipeline

#### Jenkins Agent Requirements:
- [ ] `gcloud` CLI installed
- [ ] `docker` installed
- [ ] `gsutil` installed

### Test Jenkins connectivity:
Create a test pipeline job:
```groovy
pipeline {
    agent any
    environment {
        GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-service-account-key')
    }
    stages {
        stage('Test') {
            steps {
                sh '''
                    gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS
                    gcloud config set project vhealth-dev
                    gsutil ls gs://vhealth-dev-models/
                    gcloud artifacts repositories list --location=asia-southeast1
                '''
            }
        }
    }
}
```

**Status:** [ ] Credentials configured  [ ] Test pipeline passed

---

## 7. ✅ Network Configuration

### VPC Connector (if using private Cloud SQL):
```bash
# Dev
gcloud compute networks vpc-access connectors describe vhealth-vpc-conn-dev \
    --region=asia-southeast1 \
    --project=vhealth-dev

# Prod
gcloud compute networks vpc-access connectors describe vhealth-vpc-conn-prod \
    --region=asia-southeast1 \
    --project=vhealth-prod
```

**Status:** [ ] Dev  [ ] Prod (or N/A if using public IP)

---

## 8. ✅ Pre-Deployment Tests

### Local testing:
```bash
# Build Docker image locally
docker build -t health-api:test .

# Run with local environment
docker run -p 8000:8000 \
    -e DATABASE_URL="your-connection-string" \
    -e GCP_PROJECT_ID="vhealth-dev" \
    -e GCP_MODEL_BUCKET="vhealth-dev-models" \
    health-api:test

# Test Q&A endpoint
curl -X POST http://localhost:8000/api/v1/qa/ask \
    -H "Content-Type: application/json" \
    -d '{"question": "Diabetes là gì?"}'
```

**Status:** [ ] Local build successful  [ ] Local tests passed

---

## 9. ✅ Deployment Readiness

### Code review:
- [ ] All changes committed and pushed
- [ ] Branch: `feat/ehance-tin-branch`
- [ ] Pull request created and reviewed
- [ ] No linting errors
- [ ] Tests passing

### Documentation:
- [ ] README updated
- [ ] QA_FEATURE_IMPLEMENTATION_SUMMARY.md reviewed
- [ ] API documentation updated

### Monitoring setup:
- [ ] Cloud Logging configured
- [ ] Error reporting enabled
- [ ] Alerts configured (optional)

**Status:** [ ] Ready for deployment

---

## 10. ✅ Deployment Execution

### Deploy to Dev first:
1. Go to Jenkins
2. Select the deployment pipeline
3. Configure parameters:
   - Environment: `dev`
   - Branch: `feat/ehance-tin-branch`
4. Click "Build"
5. Monitor logs

### Verify Dev deployment:
```bash
# Check Cloud Run service
gcloud run services describe vhealth-backend-dev \
    --region=asia-southeast1 \
    --project=vhealth-dev

# Get service URL
SERVICE_URL=$(gcloud run services describe vhealth-backend-dev \
    --region=asia-southeast1 \
    --project=vhealth-dev \
    --format='value(status.url)')

# Test health endpoint
curl ${SERVICE_URL}/health

# Test Q&A endpoint (requires authentication)
curl -X POST ${SERVICE_URL}/api/v1/qa/ask \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer YOUR_TOKEN" \
    -d '{"question": "Diabetes là gì?"}'
```

### If Dev is successful, deploy to Prod:
1. Same process as Dev
2. Environment: `prod`
3. Branch: `main` or `master` (after merging PR)

**Status:** [ ] Dev deployed  [ ] Dev verified  [ ] Prod deployed  [ ] Prod verified

---

## Quick Command Reference

### Check all resources at once:

```bash
# Dev environment
echo "=== GCS Buckets ==="
gsutil ls gs://vhealth-dev-models/ 2>&1

echo -e "\n=== Secrets ==="
gcloud secrets list --project=vhealth-dev --filter="name:vhealth-dev" --limit=10

echo -e "\n=== Cloud SQL ==="
gcloud sql instances list --project=vhealth-dev

echo -e "\n=== Artifact Registry ==="
gcloud artifacts repositories list --location=asia-southeast1 --project=vhealth-dev

echo -e "\n=== Cloud Run ==="
gcloud run services list --region=asia-southeast1 --project=vhealth-dev
```

### Quick health check after deployment:
```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe vhealth-backend-dev \
    --region=asia-southeast1 \
    --project=vhealth-dev \
    --format='value(status.url)')

echo "Service URL: ${SERVICE_URL}"

# Test endpoints
echo -e "\n=== Health Check ==="
curl ${SERVICE_URL}/health

echo -e "\n=== API Docs ==="
echo "Visit: ${SERVICE_URL}/docs"
```

---

## Troubleshooting

### Common Issues:

1. **Model files not loading:**
   - Check GCS bucket permissions
   - Verify model files exist in correct path
   - Check Cloud Run service account has `objectViewer` role

2. **Database connection fails:**
   - Verify Cloud SQL instance is running
   - Check DATABASE_URL secret is correct
   - Ensure Cloud SQL connector is working (if using private IP)
   - Verify service account has `cloudsql.client` role

3. **Secrets not accessible:**
   - Check secret names match exactly
   - Verify service account has `secretmanager.secretAccessor` role
   - Ensure secrets exist in correct project

4. **Docker build fails:**
   - Check Dockerfile syntax
   - Verify all dependencies in requirements.txt
   - Check for file size limits

5. **Deployment timeout:**
   - Increase Cloud Run timeout (currently 300s)
   - Check if model download takes too long
   - Consider pre-warming the model

### Viewing logs:
```bash
# Dev
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=vhealth-backend-dev" \
    --project=vhealth-dev \
    --limit=50 \
    --format=json

# Or use Cloud Console
# https://console.cloud.google.com/run?project=vhealth-dev
```

---

## Sign-off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | | | |
| Reviewer | | | |
| DevOps | | | |

**Deployment Date:** _________________

**Environment:** [ ] Dev  [ ] Prod

**Version/Commit:** _________________

**Notes:**
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________

