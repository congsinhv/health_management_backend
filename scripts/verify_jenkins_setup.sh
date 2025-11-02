#!/bin/bash
# Script to verify Jenkins setup and GCP credentials

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Jenkins Setup Verification ===${NC}\n"

echo -e "${BLUE}This script helps verify that Jenkins is properly configured for deployment.${NC}\n"

# Check 1: GCP Credentials
echo -e "${YELLOW}1. GCP Service Account Credentials${NC}"
echo -e "${BLUE}   Jenkins needs a GCP service account credential named: 'gcp-service-account-key'${NC}"
echo ""
echo "   The service account should have these roles:"
echo "   - Cloud Run Admin"
echo "   - Cloud Build Editor"
echo "   - Artifact Registry Writer"
echo "   - Storage Admin (for GCS)"
echo "   - Secret Manager Secret Accessor"
echo "   - Service Account User"
echo ""
echo "   To create the service account:"
echo -e "${GREEN}"
cat << 'EOF'
# For Dev environment
gcloud iam service-accounts create jenkins-deployer-dev \
    --display-name="Jenkins Deployer Dev" \
    --project=vhealth-dev

# Grant necessary roles
for role in \
    roles/run.admin \
    roles/cloudbuild.builds.editor \
    roles/artifactregistry.writer \
    roles/storage.admin \
    roles/secretmanager.secretAccessor \
    roles/iam.serviceAccountUser; do
    gcloud projects add-iam-policy-binding vhealth-dev \
        --member="serviceAccount:jenkins-deployer-dev@vhealth-dev.iam.gserviceaccount.com" \
        --role="$role"
done

# Create and download key
gcloud iam service-accounts keys create jenkins-sa-key-dev.json \
    --iam-account=jenkins-deployer-dev@vhealth-dev.iam.gserviceaccount.com

# Repeat for Prod environment
gcloud iam service-accounts create jenkins-deployer-prod \
    --display-name="Jenkins Deployer Prod" \
    --project=vhealth-prod

for role in \
    roles/run.admin \
    roles/cloudbuild.builds.editor \
    roles/artifactregistry.writer \
    roles/storage.admin \
    roles/secretmanager.secretAccessor \
    roles/iam.serviceAccountUser; do
    gcloud projects add-iam-policy-binding vhealth-prod \
        --member="serviceAccount:jenkins-deployer-prod@vhealth-prod.iam.gserviceaccount.com" \
        --role="$role"
done

gcloud iam service-accounts keys create jenkins-sa-key-prod.json \
    --iam-account=jenkins-deployer-prod@vhealth-prod.iam.gserviceaccount.com
EOF
echo -e "${NC}"

read -p "Press Enter to continue..."
echo ""

# Check 2: Jenkins Credentials Setup
echo -e "${YELLOW}2. Jenkins Credentials Configuration${NC}"
echo -e "${BLUE}   In Jenkins, go to: Manage Jenkins > Manage Credentials${NC}"
echo ""
echo "   Add a new credential:"
echo "   - Kind: Secret file"
echo "   - File: Upload the jenkins-sa-key-dev.json or jenkins-sa-key-prod.json"
echo "   - ID: gcp-service-account-key"
echo "   - Description: GCP Service Account for deployments"
echo ""

read -p "Press Enter to continue..."
echo ""

# Check 3: Required Jenkins Plugins
echo -e "${YELLOW}3. Required Jenkins Plugins${NC}"
echo -e "${BLUE}   Ensure these plugins are installed:${NC}"
echo "   - Pipeline"
echo "   - Git"
echo "   - Credentials Binding"
echo "   - Google Cloud SDK (gcloud)"
echo "   - Docker Pipeline"
echo ""

read -p "Press Enter to continue..."
echo ""

# Check 4: Jenkins Environment
echo -e "${YELLOW}4. Jenkins System Configuration${NC}"
echo -e "${BLUE}   Verify gcloud CLI is installed on Jenkins agent:${NC}"
echo ""
echo "   Run this in Jenkins agent:"
echo -e "${GREEN}"
cat << 'EOF'
# Test gcloud installation
gcloud version

# Test Docker installation
docker --version

# Test gsutil installation
gsutil version
EOF
echo -e "${NC}"

read -p "Press Enter to continue..."
echo ""

# Check 5: Test Connection
echo -e "${YELLOW}5. Test GCP Connection from Jenkins${NC}"
echo -e "${BLUE}   Create a test Jenkins job with this script:${NC}"
echo ""
echo -e "${GREEN}"
cat << 'EOF'
pipeline {
    agent any
    environment {
        GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-service-account-key')
    }
    stages {
        stage('Test GCP Connection') {
            steps {
                sh '''
                    gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS
                    gcloud config set project vhealth-dev
                    
                    echo "=== Testing GCS Access ==="
                    gsutil ls gs://vhealth-dev-models/ || echo "Bucket not found"
                    
                    echo "=== Testing Artifact Registry Access ==="
                    gcloud artifacts repositories list --location=asia-southeast1
                    
                    echo "=== Testing Secret Manager Access ==="
                    gcloud secrets list --filter="name:vhealth-dev" --limit=5
                    
                    echo "=== Testing Cloud Run Access ==="
                    gcloud run services list --region=asia-southeast1
                '''
            }
        }
    }
}
EOF
echo -e "${NC}"

read -p "Press Enter to continue..."
echo ""

# Check 6: GCS Buckets
echo -e "${YELLOW}6. Verify GCS Buckets${NC}"
echo -e "${BLUE}   Run this to verify model buckets exist:${NC}"
echo ""
echo -e "${GREEN}"
echo "gsutil ls gs://vhealth-dev-models/"
echo "gsutil ls gs://vhealth-prod-models/"
echo -e "${NC}"

read -p "Want to test now? (y/N): " test_choice
if [[ $test_choice =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${YELLOW}Testing Dev bucket:${NC}"
    gsutil ls gs://vhealth-dev-models/ 2>&1 && echo -e "${GREEN}✓ Dev bucket accessible${NC}" || echo -e "${RED}✗ Dev bucket not accessible${NC}"
    
    echo ""
    echo -e "${YELLOW}Testing Prod bucket:${NC}"
    gsutil ls gs://vhealth-prod-models/ 2>&1 && echo -e "${GREEN}✓ Prod bucket accessible${NC}" || echo -e "${RED}✗ Prod bucket not accessible${NC}"
fi

echo ""
echo -e "${GREEN}=== Verification Guide Complete ===${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Ensure all credentials are configured in Jenkins"
echo "2. Run the test pipeline to verify connectivity"
echo "3. If tests pass, proceed with actual deployment"
echo ""
echo -e "${BLUE}For actual deployment, use:${NC}"
echo "  - Branch: feat/ehance-tin-branch (or your target branch)"
echo "  - Environment: dev (test first)"
echo "  - Monitor logs carefully"

