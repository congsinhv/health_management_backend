# Deployment Scripts Guide

This directory contains scripts to help with pre-deployment setup and verification.

## Quick Start

### 1. Check if you're ready to deploy
```bash
./scripts/check_deployment_readiness.sh
```
This comprehensive script checks all prerequisites:
- ✅ GCS model buckets
- ✅ Model files uploaded
- ✅ Secret Manager secrets
- ✅ Cloud SQL database
- ✅ Artifact Registry
- ✅ Service accounts and IAM
- ✅ VPC connectors
- ✅ Cloud Run services
- ✅ Required APIs enabled

**Exit codes:**
- `0` = Ready for deployment (90%+ checks passed)
- `1` = Issues need attention

---

## Individual Setup Scripts

### 2. Setup GCS Buckets
```bash
./scripts/setup_gcs_buckets.sh
```
**What it does:**
- Creates `vhealth-dev-models` and `vhealth-prod-models` buckets
- Enables versioning
- Sets lifecycle policies
- Configures IAM permissions for Cloud Run service accounts

**When to use:** First-time setup or if buckets don't exist

---

### 3. Upload Model Files
```bash
./scripts/upload_models_to_gcs.sh
```
**What it does:**
- Uploads Vietnamese SBERT model files to GCS
- Verifies upload completion
- Shows file sizes and counts

**Prerequisites:**
- Model files exist in `models/vietnamese-sbert/` directory
- Or download from: `git clone https://huggingface.co/keepitreal/vietnamese-sbert models/vietnamese-sbert`

**When to use:** Initial setup or when updating model files

---

### 4. Setup Secrets
```bash
./scripts/setup_secrets.sh
```
**What it does:**
- Creates/updates all required Secret Manager secrets
- Grants access to Cloud Run service accounts
- Interactive prompts for secret values

**Required secrets for each environment:**
- `vhealth-{env}-database-url` - PostgreSQL connection string
- `vhealth-{env}-secret-key` - JWT secret key
- `vhealth-{env}-google-client-id` - Google OAuth client ID
- `vhealth-{env}-google-client-secret` - Google OAuth client secret
- `vhealth-{env}-mail-username` - SMTP username
- `vhealth-{env}-mail-password` - SMTP password

**When to use:** Initial setup or when rotating secrets

---

### 5. Verify Jenkins Setup
```bash
./scripts/verify_jenkins_setup.sh
```
**What it does:**
- Provides step-by-step guide for Jenkins configuration
- Shows how to create Jenkins service accounts
- Provides test pipeline script
- Checks GCP connectivity

**When to use:** Setting up Jenkins for the first time or troubleshooting deployments

---

## Documentation

### Pre-Deployment Checklist
```bash
cat scripts/PRE_DEPLOYMENT_CHECKLIST.md
```
Comprehensive checklist covering:
- All required GCP resources
- Configuration verification steps
- Manual commands for each check
- Troubleshooting guide
- Sign-off section

**When to use:** Before any deployment, especially to production

---

## Typical Workflow

### First-Time Setup (Dev Environment)

```bash
# 1. Check what's missing
./scripts/check_deployment_readiness.sh
# Select: 1 (Dev only)

# 2. Setup GCS buckets
./scripts/setup_gcs_buckets.sh
# Select: 1 (Dev only)

# 3. Upload model files
./scripts/upload_models_to_gcs.sh
# Select: 1 (Dev only)

# 4. Setup secrets (interactive)
./scripts/setup_secrets.sh
# Select: 1 (Setup Dev secrets)

# 5. Verify Jenkins
./scripts/verify_jenkins_setup.sh
# Follow the guide

# 6. Final check
./scripts/check_deployment_readiness.sh
# Should show 90%+ success rate

# 7. Deploy via Jenkins
# Go to Jenkins > Select pipeline > Build with parameters
# Environment: dev
# Branch: feat/ehance-tin-branch
```

### Deploying to Production

```bash
# 1. Ensure Dev is working
# Test all endpoints in dev environment

# 2. Setup Prod resources
./scripts/check_deployment_readiness.sh
# Select: 2 (Prod only)

# 3. Setup buckets if needed
./scripts/setup_gcs_buckets.sh
# Select: 2 (Prod only)

# 4. Upload models to prod
./scripts/upload_models_to_gcs.sh
# Select: 2 (Prod only)

# 5. Setup prod secrets
./scripts/setup_secrets.sh
# Select: 2 (Setup Prod secrets)
# IMPORTANT: Use different secret values than dev!

# 6. Final verification
./scripts/check_deployment_readiness.sh
# Select: 2 (Prod only)

# 7. Deploy via Jenkins
# Merge PR to main/master first
# Then deploy via Jenkins
# Environment: prod
# Branch: main (or master)
```

---

## Manual Verification Commands

### Quick health checks:

```bash
# Check GCS buckets
gsutil ls gs://vhealth-dev-models/models/vietnamese-sbert/
gsutil ls gs://vhealth-prod-models/models/vietnamese-sbert/

# Check secrets
gcloud secrets list --project=vhealth-dev --filter="name:vhealth-dev"
gcloud secrets list --project=vhealth-prod --filter="name:vhealth-prod"

# Check Cloud SQL
gcloud sql instances list --project=vhealth-dev
gcloud sql instances list --project=vhealth-prod

# Check Artifact Registry
gcloud artifacts repositories list --location=asia-southeast1 --project=vhealth-dev
gcloud artifacts repositories list --location=asia-southeast1 --project=vhealth-prod

# Check Cloud Run services
gcloud run services list --region=asia-southeast1 --project=vhealth-dev
gcloud run services list --region=asia-southeast1 --project=vhealth-prod
```

### Test deployed service:

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe vhealth-backend-dev \
    --region=asia-southeast1 \
    --project=vhealth-dev \
    --format='value(status.url)')

# Test health endpoint
curl ${SERVICE_URL}/health

# Open API documentation
open ${SERVICE_URL}/docs

# Test Q&A endpoint (with auth token)
curl -X POST ${SERVICE_URL}/api/v1/qa/ask \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer YOUR_TOKEN" \
    -d '{"question": "Diabetes là gì?"}'
```

---

## Troubleshooting

### Script fails with "Permission denied"
```bash
chmod +x scripts/*.sh
```

### "gcloud: command not found"
```bash
# Install Google Cloud SDK
# https://cloud.google.com/sdk/docs/install

# Or use Cloud Shell (pre-installed)
```

### "Bucket already exists but in different project"
- Use unique bucket names
- Or delete bucket from other project first

### Secrets not accessible from Cloud Run
```bash
# Check service account has correct role
SA="vhealth-backend-dev@vhealth-dev.iam.gserviceaccount.com"
SECRET="vhealth-dev-database-url"

gcloud secrets add-iam-policy-binding ${SECRET} \
    --project=vhealth-dev \
    --member="serviceAccount:${SA}" \
    --role="roles/secretmanager.secretAccessor"
```

### Model fails to load from GCS
```bash
# Check bucket permissions
gsutil iam get gs://vhealth-dev-models/

# Grant service account read access
gsutil iam ch serviceAccount:vhealth-backend-dev@vhealth-dev.iam.gserviceaccount.com:objectViewer \
    gs://vhealth-dev-models
```

---

## Environment Information

### Dev Environment
- **Project:** `vhealth-dev`
- **Region:** `asia-southeast1` (Singapore)
- **Model Bucket:** `vhealth-dev-models`
- **Artifact Registry:** `vhealth-backend-dev`
- **Cloud Run:** `vhealth-backend-dev`
- **Cloud SQL:** `vhealth-backend-db-dev`

### Prod Environment
- **Project:** `vhealth-prod`
- **Region:** `asia-southeast1` (Singapore)
- **Model Bucket:** `vhealth-prod-models`
- **Artifact Registry:** `vhealth-backend-prod`
- **Cloud Run:** `vhealth-backend-prod`
- **Cloud SQL:** `vhealth-backend-db-prod`

---

## Security Best Practices

1. **Never commit secrets to git**
   - Use Secret Manager for all sensitive data
   - Add `.env` files to `.gitignore`

2. **Use different secrets for dev/prod**
   - Different JWT keys
   - Different OAuth credentials
   - Different database passwords

3. **Rotate secrets regularly**
   - Update via `./scripts/setup_secrets.sh`
   - Cloud Run will pick up new versions automatically

4. **Limit IAM permissions**
   - Service accounts should have minimum required roles
   - Use separate service accounts for dev/prod

5. **Monitor access logs**
   - Enable Cloud Audit Logs
   - Review Secret Manager access logs
   - Set up alerts for suspicious activity

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs: `gcloud logging read ...`
3. Check GCP Console for visual debugging
4. Review `scripts/PRE_DEPLOYMENT_CHECKLIST.md`

## Related Documentation
- [QA Feature Implementation](../QA_FEATURE_IMPLEMENTATION_SUMMARY.md)
- [Terraform Setup](../terraform/README.md)
- [Jenkins Pipeline](../Jenkinsfile)
- [Main README](../README.md)

