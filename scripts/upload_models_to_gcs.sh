#!/bin/bash
# Script to upload Vietnamese SBERT model files to GCS

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DEV_BUCKET="vhealth-dev-models"
PROD_BUCKET="vhealth-prod-models"
MODEL_SOURCE="models/vietnamese-sbert"
MODEL_DEST="models/vietnamese-sbert"

echo -e "${YELLOW}=== Upload ML Models to GCS ===${NC}\n"

# Check if model directory exists locally
if [ ! -d "${MODEL_SOURCE}" ]; then
    echo -e "${RED}✗ Local model directory not found: ${MODEL_SOURCE}${NC}"
    echo -e "${YELLOW}Options:${NC}"
    echo "1. Download from original source"
    echo "2. Copy from existing GCS bucket"
    echo ""
    echo "To download from Hugging Face:"
    echo "  git clone https://huggingface.co/keepitreal/vietnamese-sbert ${MODEL_SOURCE}"
    exit 1
fi

# Show model files to be uploaded
echo -e "${YELLOW}Model files to upload:${NC}"
ls -lh ${MODEL_SOURCE}
echo ""

# Get total size
TOTAL_SIZE=$(du -sh ${MODEL_SOURCE} | cut -f1)
echo -e "${YELLOW}Total size: ${TOTAL_SIZE}${NC}\n"

# Function to upload models
upload_models() {
    local bucket=$1
    local env=$2
    
    echo -e "${YELLOW}Uploading models to ${env} bucket: gs://${bucket}/${MODEL_DEST}/${NC}"
    
    # Use -m for parallel upload, -r for recursive
    gsutil -m cp -r ${MODEL_SOURCE}/* gs://${bucket}/${MODEL_DEST}/
    
    echo -e "${GREEN}✓ Upload complete${NC}"
    
    # Verify upload
    echo -e "\n${YELLOW}Verifying upload:${NC}"
    gsutil ls -lh gs://${bucket}/${MODEL_DEST}/
    
    echo -e "\n${GREEN}✓ Files verified in ${env} bucket${NC}\n"
}

# Main execution
echo -e "${YELLOW}Select target environment:${NC}"
echo "1) Dev only (vhealth-dev-models)"
echo "2) Prod only (vhealth-prod-models)"
echo "3) Both"
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        upload_models ${DEV_BUCKET} "dev"
        ;;
    2)
        upload_models ${PROD_BUCKET} "prod"
        ;;
    3)
        upload_models ${DEV_BUCKET} "dev"
        upload_models ${PROD_BUCKET} "prod"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo -e "${GREEN}=== Upload Complete ===${NC}"
echo -e "\n${YELLOW}Verify the upload:${NC}"
echo "gsutil ls -r gs://${DEV_BUCKET}/${MODEL_DEST}/"
echo ""
echo -e "${YELLOW}Test download (optional):${NC}"
echo "gsutil cp gs://${DEV_BUCKET}/${MODEL_DEST}/config.json /tmp/test-config.json"

