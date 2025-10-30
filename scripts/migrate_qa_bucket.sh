#!/bin/bash
# Migration script to copy Q&A files from temp bucket to primary bucket
# Usage: ./scripts/migrate_qa_bucket.sh <source-bucket> <destination-bucket>
#
# Example:
#   ./scripts/migrate_qa_bucket.sh vhealth-qa-temp-20251030 vhealth-qa-prod

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if required arguments are provided
if [ $# -ne 2 ]; then
    echo -e "${RED}Error: Missing required arguments${NC}"
    echo "Usage: $0 <source-bucket> <destination-bucket>"
    echo ""
    echo "Example:"
    echo "  $0 vhealth-qa-temp-20251030 vhealth-qa-prod"
    exit 1
fi

SOURCE_BUCKET=$1
DEST_BUCKET=$2

echo -e "${YELLOW}==================================${NC}"
echo -e "${YELLOW}Q&A Bucket Migration Script${NC}"
echo -e "${YELLOW}==================================${NC}"
echo ""
echo -e "Source Bucket: ${GREEN}gs://${SOURCE_BUCKET}${NC}"
echo -e "Destination Bucket: ${GREEN}gs://${DEST_BUCKET}${NC}"
echo ""

# Verify source bucket exists
echo -e "${YELLOW}Verifying source bucket...${NC}"
if ! gsutil ls gs://${SOURCE_BUCKET}/ &> /dev/null; then
    echo -e "${RED}Error: Source bucket gs://${SOURCE_BUCKET}/ does not exist or is not accessible${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Source bucket exists${NC}"
echo ""

# Check if destination bucket exists, create if not
echo -e "${YELLOW}Checking destination bucket...${NC}"
if ! gsutil ls gs://${DEST_BUCKET}/ &> /dev/null; then
    echo -e "${YELLOW}Destination bucket does not exist. Creating...${NC}"
    read -p "Create bucket gs://${DEST_BUCKET}/ in us-central1? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        PROJECT_ID=$(gcloud config get-value project)
        gsutil mb -p ${PROJECT_ID} -c STANDARD -l us-central1 gs://${DEST_BUCKET}/
        echo -e "${GREEN}✓ Destination bucket created${NC}"
    else
        echo -e "${RED}Migration cancelled${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ Destination bucket exists${NC}"
fi
echo ""

# Show files to be copied
echo -e "${YELLOW}Files to be migrated:${NC}"
gsutil ls -r gs://${SOURCE_BUCKET}/ | grep -v "/:$" || true
echo ""

# Confirm migration
read -p "Proceed with migration? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${RED}Migration cancelled${NC}"
    exit 1
fi

# Copy data directory
echo -e "${YELLOW}Copying data files...${NC}"
gsutil -m cp -r gs://${SOURCE_BUCKET}/data/* gs://${DEST_BUCKET}/data/
echo -e "${GREEN}✓ Data files copied${NC}"
echo ""

# Copy models directory
echo -e "${YELLOW}Copying model files...${NC}"
gsutil -m cp -r gs://${SOURCE_BUCKET}/models/* gs://${DEST_BUCKET}/models/
echo -e "${GREEN}✓ Model files copied${NC}"
echo ""

# Verify migration
echo -e "${YELLOW}Verifying migration...${NC}"
SOURCE_COUNT=$(gsutil ls -r gs://${SOURCE_BUCKET}/ | grep -v "/:$" | wc -l)
DEST_COUNT=$(gsutil ls -r gs://${DEST_BUCKET}/ | grep -v "/:$" | wc -l)

echo -e "Source files: ${GREEN}${SOURCE_COUNT}${NC}"
echo -e "Destination files: ${GREEN}${DEST_COUNT}${NC}"

if [ "$SOURCE_COUNT" -eq "$DEST_COUNT" ]; then
    echo -e "${GREEN}✓ Migration verified successfully${NC}"
else
    echo -e "${YELLOW}⚠ Warning: File counts don't match. Please verify manually.${NC}"
fi
echo ""

# Ask if temp bucket should be deleted
echo -e "${YELLOW}Migration complete!${NC}"
echo ""
read -p "Delete temporary source bucket gs://${SOURCE_BUCKET}/ ? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Deleting temporary bucket...${NC}"
    gsutil -m rm -r gs://${SOURCE_BUCKET}/
    echo -e "${GREEN}✓ Temporary bucket deleted${NC}"
else
    echo -e "${YELLOW}Temporary bucket preserved: gs://${SOURCE_BUCKET}/${NC}"
    echo -e "${YELLOW}You can delete it manually later with: gsutil -m rm -r gs://${SOURCE_BUCKET}/${NC}"
fi

echo ""
echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}Migration Complete!${NC}"
echo -e "${GREEN}==================================${NC}"
echo ""
echo -e "Next steps:"
echo -e "1. Update your environment variables to use: ${GREEN}gs://${DEST_BUCKET}${NC}"
echo -e "2. Set ${GREEN}QA_GCS_BUCKET=${DEST_BUCKET}${NC} in your Cloud Run configuration"
echo -e "3. Deploy your application"

