#!/bin/bash
# Terraform State Fix Script
# This script imports existing GCP resources into Terraform state and completes deployment

set -e  # Exit on error

cd "$(dirname "$0")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== VHealth Production Terraform State Fix ===${NC}"
echo ""

# Set credentials
export GOOGLE_APPLICATION_CREDENTIALS=/Users/synh/vhealth-prod-sa-key.json

if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo -e "${RED}Error: Service account key not found at $GOOGLE_APPLICATION_CREDENTIALS${NC}"
    exit 1
fi

echo -e "${YELLOW}Using service account: $GOOGLE_APPLICATION_CREDENTIALS${NC}"
echo ""

# Function to import resource if it exists
import_resource() {
    local tf_resource=$1
    local gcp_resource=$2
    local resource_name=$3

    echo -e "${YELLOW}Importing $resource_name...${NC}"

    if terraform import \
        -var-file="environments/prod.tfvars" \
        -var-file="environments/prod.auto.tfvars" \
        "$tf_resource" \
        "$gcp_resource" 2>&1 | grep -q "successfully imported\|already managed"; then
        echo -e "${GREEN}✓ $resource_name imported/exists${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed to import $resource_name${NC}"
        return 1
    fi
}

echo -e "${GREEN}Step 1: Importing existing resources into Terraform state${NC}"
echo "================================================================"
echo ""

# Import service accounts
import_resource \
    "google_service_account.cloud_run_sa" \
    "projects/vhealth-prod/serviceAccounts/vhealth-backend-prod@vhealth-prod.iam.gserviceaccount.com" \
    "Cloud Run Service Account"

import_resource \
    "google_service_account.cloud_scheduler_sa" \
    "projects/vhealth-prod/serviceAccounts/vhealth-scheduler-prod@vhealth-prod.iam.gserviceaccount.com" \
    "Cloud Scheduler Service Account"

# Import Cloud SQL
import_resource \
    "module.cloud_sql.google_sql_database_instance.instance" \
    "vhealth-prod/vhealth-backend-db-prod" \
    "Cloud SQL Instance"

# Import VPC Connector
import_resource \
    "module.vpc_connector.google_vpc_access_connector.connector" \
    "projects/vhealth-prod/locations/asia-southeast1/connectors/vhealth-vpc-conn-prod" \
    "VPC Connector"

# Import Redis instance (if exists)
if gcloud redis instances describe vhealth-cache-prod \
    --region=asia-southeast1 \
    --project=vhealth-prod &>/dev/null; then
    import_resource \
        "module.memorystore.google_redis_instance.cache" \
        "projects/vhealth-prod/locations/asia-southeast1/instances/vhealth-cache-prod" \
        "Redis Instance"
fi

# Import Redis auth secret (if exists)
if gcloud secrets describe vhealth-cache-prod-auth-string \
    --project=vhealth-prod &>/dev/null; then
    import_resource \
        "module.memorystore.google_secret_manager_secret.redis_auth" \
        "projects/878309847532/secrets/vhealth-cache-prod-auth-string" \
        "Redis Auth Secret"
fi

echo ""
echo -e "${GREEN}Step 2: Running Terraform plan${NC}"
echo "================================================================"
echo ""

if terraform plan \
    -var-file="environments/prod.tfvars" \
    -var-file="environments/prod.auto.tfvars" \
    -out=tfplan-fix; then
    echo -e "${GREEN}✓ Terraform plan successful${NC}"
else
    echo -e "${RED}✗ Terraform plan failed${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}Resources to be created:${NC}"
terraform show tfplan-fix | grep -A 1 "will be created" | head -20 || true

echo ""
read -p "Do you want to apply these changes? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo -e "${YELLOW}Deployment cancelled${NC}"
    exit 0
fi

echo ""
echo -e "${GREEN}Step 3: Applying Terraform changes${NC}"
echo "================================================================"
echo ""

if terraform apply tfplan-fix; then
    echo ""
    echo -e "${GREEN}✓ Terraform apply successful!${NC}"
else
    echo ""
    echo -e "${RED}✗ Terraform apply failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Step 4: Deployment verification${NC}"
echo "================================================================"
echo ""

# Get outputs
echo -e "${YELLOW}Terraform Outputs:${NC}"
terraform output

echo ""
echo -e "${GREEN}Step 5: Resource verification${NC}"
echo "================================================================"
echo ""

# Verify Cloud SQL
echo -e "${YELLOW}Cloud SQL Instance:${NC}"
gcloud sql instances describe vhealth-backend-db-prod \
    --project=vhealth-prod \
    --format="value(state,settings.tier,ipAddresses[0].ipAddress)" | \
    awk '{print "  State: "$1"\n  Tier: "$2"\n  IP: "$3}'

# Verify VPC Connector
echo ""
echo -e "${YELLOW}VPC Connector:${NC}"
gcloud compute networks vpc-access connectors describe vhealth-vpc-conn-prod \
    --region=asia-southeast1 \
    --project=vhealth-prod \
    --format="value(state,ipCidrRange)" | \
    awk '{print "  State: "$1"\n  IP Range: "$2}'

# Verify Redis
echo ""
echo -e "${YELLOW}Redis Instance:${NC}"
gcloud redis instances describe vhealth-cache-prod \
    --region=asia-southeast1 \
    --project=vhealth-prod \
    --format="value(state,tier,memorySizeGb,host)" 2>/dev/null | \
    awk '{print "  State: "$1"\n  Tier: "$2"\n  Memory: "$3"GB\n  Host: "$4}' || \
    echo "  Not yet created"

# Verify Artifact Registry
echo ""
echo -e "${YELLOW}Artifact Registry:${NC}"
gcloud artifacts repositories describe vhealth-backend-prod \
    --location=asia-southeast1 \
    --project=vhealth-prod \
    --format="value(name,format)" 2>/dev/null | \
    awk '{print "  Repository: "$1"\n  Format: "$2}' || \
    echo "  Not yet created"

echo ""
echo -e "${GREEN}=== Deployment Complete! ===${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "  1. Upload Q&A models to GCS"
echo "  2. Build and push Docker images"
echo "  3. Deploy application to Cloud Run"
echo "  4. Run database migrations"
echo ""
echo -e "${YELLOW}Quick Commands:${NC}"
echo "  # List all secrets"
echo "  gcloud secrets list --project=vhealth-prod"
echo ""
echo "  # View infrastructure state"
echo "  terraform state list"
echo ""
echo "  # Get Cloud SQL connection details"
echo "  terraform output cloud_sql_public_ip"
echo ""
