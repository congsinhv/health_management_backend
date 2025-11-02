#!/bin/bash
# Script to create and verify GCS buckets for ML models

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DEV_PROJECT="vhealth-dev"
PROD_PROJECT="vhealth-prod"
REGION="asia-southeast1"
DEV_BUCKET="vhealth-dev-models"
PROD_BUCKET="vhealth-prod-models"

echo -e "${YELLOW}=== GCS Model Buckets Setup ===${NC}\n"

# Function to check and create bucket
check_and_create_bucket() {
    local project=$1
    local bucket=$2
    local env=$3
    
    echo -e "${YELLOW}Checking ${env} bucket: ${bucket}${NC}"
    
    # Set the project
    gcloud config set project ${project}
    
    # Check if bucket exists
    if gsutil ls -b gs://${bucket} &> /dev/null; then
        echo -e "${GREEN}✓ Bucket ${bucket} exists${NC}"
        
        # Show bucket info
        echo -e "\n${YELLOW}Bucket details:${NC}"
        gsutil ls -L -b gs://${bucket} | grep -E "(Location|Storage class|Versioning)"
        
        # Check if model files exist
        echo -e "\n${YELLOW}Checking for model files:${NC}"
        if gsutil ls gs://${bucket}/models/vietnamese-sbert/ &> /dev/null; then
            echo -e "${GREEN}✓ Model directory exists${NC}"
            gsutil du -sh gs://${bucket}/models/vietnamese-sbert/
        else
            echo -e "${RED}✗ Model directory NOT found${NC}"
            echo -e "${YELLOW}  You need to upload model files to: gs://${bucket}/models/vietnamese-sbert/${NC}"
        fi
    else
        echo -e "${RED}✗ Bucket ${bucket} does NOT exist${NC}"
        echo -e "${YELLOW}Creating bucket...${NC}"
        
        # Create bucket
        gsutil mb -p ${project} -c STANDARD -l ${REGION} gs://${bucket}
        
        # Enable versioning (optional but recommended)
        gsutil versioning set on gs://${bucket}
        
        # Set lifecycle policy to delete old versions after 30 days
        cat > /tmp/lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {
          "numNewerVersions": 3,
          "isLive": false
        }
      }
    ]
  }
}
EOF
        gsutil lifecycle set /tmp/lifecycle.json gs://${bucket}
        rm /tmp/lifecycle.json
        
        echo -e "${GREEN}✓ Bucket ${bucket} created successfully${NC}"
        echo -e "${YELLOW}  Remember to upload model files!${NC}"
    fi
    echo ""
}

# Function to set IAM permissions
set_bucket_permissions() {
    local project=$1
    local bucket=$2
    local env=$3
    
    echo -e "${YELLOW}Setting IAM permissions for ${env} bucket${NC}"
    
    # Grant Cloud Run service account access to read from bucket
    SERVICE_ACCOUNT="vhealth-backend-${env}@${project}.iam.gserviceaccount.com"
    
    echo "Granting storage.objectViewer role to ${SERVICE_ACCOUNT}"
    gsutil iam ch serviceAccount:${SERVICE_ACCOUNT}:objectViewer gs://${bucket}
    
    echo -e "${GREEN}✓ Permissions set${NC}\n"
}

# Main execution
echo -e "${YELLOW}Select environment:${NC}"
echo "1) Dev only"
echo "2) Prod only"
echo "3) Both"
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        check_and_create_bucket ${DEV_PROJECT} ${DEV_BUCKET} "dev"
        set_bucket_permissions ${DEV_PROJECT} ${DEV_BUCKET} "dev"
        ;;
    2)
        check_and_create_bucket ${PROD_PROJECT} ${PROD_BUCKET} "prod"
        set_bucket_permissions ${PROD_PROJECT} ${PROD_BUCKET} "prod"
        ;;
    3)
        check_and_create_bucket ${DEV_PROJECT} ${DEV_BUCKET} "dev"
        set_bucket_permissions ${DEV_PROJECT} ${DEV_BUCKET} "dev"
        check_and_create_bucket ${PROD_PROJECT} ${PROD_BUCKET} "prod"
        set_bucket_permissions ${PROD_PROJECT} ${PROD_BUCKET} "prod"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo -e "${GREEN}=== Setup Complete ===${NC}"
echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Upload model files if not already present:"
echo "   gsutil -m cp -r models/vietnamese-sbert/* gs://${DEV_BUCKET}/models/vietnamese-sbert/"
echo "2. Verify files were uploaded:"
echo "   gsutil ls -r gs://${DEV_BUCKET}/models/vietnamese-sbert/"

