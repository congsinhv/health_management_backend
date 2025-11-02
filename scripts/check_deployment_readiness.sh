#!/bin/bash
# Comprehensive script to check deployment readiness
# This script checks all prerequisites for deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DEV_PROJECT="vhealth-dev"
PROD_PROJECT="vhealth-prod"
REGION="asia-southeast1"
DEV_BUCKET="vhealth-dev-models"
PROD_BUCKET="vhealth-prod-models"

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

echo -e "${YELLOW}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════╗
║     VHealth Deployment Readiness Checker                  ║
╚═══════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}\n"

# Function to log check results
log_check() {
    local status=$1
    local message=$2
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    if [ "$status" = "pass" ]; then
        echo -e "${GREEN}✓${NC} $message"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    elif [ "$status" = "fail" ]; then
        echo -e "${RED}✗${NC} $message"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    elif [ "$status" = "warn" ]; then
        echo -e "${YELLOW}⚠${NC} $message"
    else
        echo -e "${BLUE}ℹ${NC} $message"
    fi
}

# Select environment
echo -e "${YELLOW}Select environment to check:${NC}"
echo "1) Dev"
echo "2) Prod"
echo "3) Both"
read -p "Enter choice [1-3]: " env_choice

case $env_choice in
    1)
        CHECK_DEV=true
        CHECK_PROD=false
        ;;
    2)
        CHECK_DEV=false
        CHECK_PROD=true
        ;;
    3)
        CHECK_DEV=true
        CHECK_PROD=true
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Function to check environment
check_environment() {
    local project=$1
    local env=$2
    local bucket=$3
    
    echo -e "\n${YELLOW}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  Checking ${env^^} Environment (${project})${NC}"
    echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}\n"
    
    # Set project
    gcloud config set project ${project} --quiet
    
    # 1. Check GCS Bucket
    echo -e "${BLUE}[1/8] GCS Model Bucket${NC}"
    if gsutil ls gs://${bucket}/ &> /dev/null; then
        log_check "pass" "Bucket ${bucket} exists"
        
        # Check for model files
        if gsutil ls gs://${bucket}/models/vietnamese-sbert/ &> /dev/null; then
            log_check "pass" "Model directory exists in bucket"
            
            # Check specific files
            MODEL_FILES=("config.json" "tokenizer_config.json" "vocab.txt" "1_Pooling/config.json")
            for file in "${MODEL_FILES[@]}"; do
                if gsutil ls gs://${bucket}/models/vietnamese-sbert/${file} &> /dev/null; then
                    log_check "pass" "Found ${file}"
                else
                    log_check "fail" "Missing ${file}"
                fi
            done
        else
            log_check "fail" "Model directory NOT found in bucket"
        fi
    else
        log_check "fail" "Bucket ${bucket} does NOT exist"
    fi
    echo ""
    
    # 2. Check Secrets
    echo -e "${BLUE}[2/8] Secret Manager Secrets${NC}"
    REQUIRED_SECRETS=(
        "vhealth-${env}-database-url"
        "vhealth-${env}-secret-key"
        "vhealth-${env}-google-client-id"
        "vhealth-${env}-google-client-secret"
        "vhealth-${env}-mail-username"
        "vhealth-${env}-mail-password"
    )
    
    for secret in "${REQUIRED_SECRETS[@]}"; do
        if gcloud secrets describe ${secret} --project=${project} &> /dev/null; then
            log_check "pass" "Secret ${secret} exists"
            
            # Check if service account has access
            SA="vhealth-backend-${env}@${project}.iam.gserviceaccount.com"
            if gcloud secrets get-iam-policy ${secret} --project=${project} 2>/dev/null | grep -q ${SA}; then
                log_check "pass" "  Service account has access"
            else
                log_check "warn" "  Service account might not have access"
            fi
        else
            log_check "fail" "Secret ${secret} does NOT exist"
        fi
    done
    echo ""
    
    # 3. Check Cloud SQL
    echo -e "${BLUE}[3/8] Cloud SQL Database${NC}"
    DB_INSTANCE="vhealth-backend-db-${env}"
    if gcloud sql instances describe ${DB_INSTANCE} --project=${project} &> /dev/null; then
        log_check "pass" "Cloud SQL instance ${DB_INSTANCE} exists"
        
        # Check if running
        STATUS=$(gcloud sql instances describe ${DB_INSTANCE} --project=${project} --format="value(state)")
        if [ "$STATUS" = "RUNNABLE" ]; then
            log_check "pass" "Instance is running"
        else
            log_check "warn" "Instance state: ${STATUS}"
        fi
        
        # Check database exists
        if gcloud sql databases list --instance=${DB_INSTANCE} --project=${project} 2>/dev/null | grep -q "health_management"; then
            log_check "pass" "Database 'health_management' exists"
        else
            log_check "fail" "Database 'health_management' NOT found"
        fi
    else
        log_check "fail" "Cloud SQL instance ${DB_INSTANCE} does NOT exist"
    fi
    echo ""
    
    # 4. Check Artifact Registry
    echo -e "${BLUE}[4/8] Artifact Registry${NC}"
    REPO="vhealth-backend-${env}"
    if gcloud artifacts repositories describe ${REPO} --location=${REGION} --project=${project} &> /dev/null; then
        log_check "pass" "Repository ${REPO} exists"
        
        # Check if images exist
        IMAGE_COUNT=$(gcloud artifacts docker images list ${REGION}-docker.pkg.dev/${project}/${REPO} --project=${project} 2>/dev/null | wc -l)
        if [ "$IMAGE_COUNT" -gt 1 ]; then
            log_check "pass" "Repository has images ($((IMAGE_COUNT - 1)) images)"
        else
            log_check "warn" "Repository is empty (no images yet)"
        fi
    else
        log_check "fail" "Repository ${REPO} does NOT exist"
    fi
    echo ""
    
    # 5. Check Service Account
    echo -e "${BLUE}[5/8] Service Account${NC}"
    SA="vhealth-backend-${env}@${project}.iam.gserviceaccount.com"
    if gcloud iam service-accounts describe ${SA} --project=${project} &> /dev/null; then
        log_check "pass" "Service account ${SA} exists"
        
        # Check key roles
        REQUIRED_ROLES=(
            "roles/cloudsql.client"
            "roles/secretmanager.secretAccessor"
        )
        
        for role in "${REQUIRED_ROLES[@]}"; do
            if gcloud projects get-iam-policy ${project} --flatten="bindings[].members" --filter="bindings.role:${role} AND bindings.members:serviceAccount:${SA}" 2>/dev/null | grep -q ${SA}; then
                log_check "pass" "  Has ${role}"
            else
                log_check "fail" "  Missing ${role}"
            fi
        done
    else
        log_check "fail" "Service account ${SA} does NOT exist"
    fi
    echo ""
    
    # 6. Check VPC Connector (if needed)
    echo -e "${BLUE}[6/8] VPC Connector${NC}"
    VPC_CONNECTOR="vhealth-vpc-conn-${env}"
    if gcloud compute networks vpc-access connectors describe ${VPC_CONNECTOR} --region=${REGION} --project=${project} &> /dev/null; then
        log_check "pass" "VPC Connector ${VPC_CONNECTOR} exists"
        
        STATUS=$(gcloud compute networks vpc-access connectors describe ${VPC_CONNECTOR} --region=${REGION} --project=${project} --format="value(state)")
        if [ "$STATUS" = "READY" ]; then
            log_check "pass" "VPC Connector is ready"
        else
            log_check "warn" "VPC Connector state: ${STATUS}"
        fi
    else
        log_check "info" "VPC Connector not found (OK if using public IP)"
    fi
    echo ""
    
    # 7. Check Cloud Run Service
    echo -e "${BLUE}[7/8] Cloud Run Service${NC}"
    SERVICE="vhealth-backend-${env}"
    if gcloud run services describe ${SERVICE} --region=${REGION} --project=${project} &> /dev/null; then
        log_check "pass" "Cloud Run service ${SERVICE} exists"
        
        # Get service URL
        SERVICE_URL=$(gcloud run services describe ${SERVICE} --region=${REGION} --project=${project} --format="value(status.url)")
        log_check "info" "Service URL: ${SERVICE_URL}"
        
        # Check if service is ready
        READY=$(gcloud run services describe ${SERVICE} --region=${REGION} --project=${project} --format="value(status.conditions[0].status)")
        if [ "$READY" = "True" ]; then
            log_check "pass" "Service is ready"
            
            # Try to ping health endpoint
            if curl -s -o /dev/null -w "%{http_code}" ${SERVICE_URL}/health | grep -q "200"; then
                log_check "pass" "Health endpoint responding"
            else
                log_check "warn" "Health endpoint not responding (might need auth)"
            fi
        else
            log_check "warn" "Service not ready"
        fi
    else
        log_check "info" "Cloud Run service not deployed yet (will be created on first deploy)"
    fi
    echo ""
    
    # 8. Check Required APIs
    echo -e "${BLUE}[8/8] Required APIs${NC}"
    REQUIRED_APIS=(
        "run.googleapis.com"
        "sqladmin.googleapis.com"
        "secretmanager.googleapis.com"
        "artifactregistry.googleapis.com"
        "cloudbuild.googleapis.com"
        "storage.googleapis.com"
    )
    
    for api in "${REQUIRED_APIS[@]}"; do
        if gcloud services list --enabled --project=${project} 2>/dev/null | grep -q ${api}; then
            log_check "pass" "${api} enabled"
        else
            log_check "fail" "${api} NOT enabled"
        fi
    done
    echo ""
}

# Run checks
if [ "$CHECK_DEV" = true ]; then
    check_environment ${DEV_PROJECT} "dev" ${DEV_BUCKET}
fi

if [ "$CHECK_PROD" = true ]; then
    check_environment ${PROD_PROJECT} "prod" ${PROD_BUCKET}
fi

# Summary
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  Summary${NC}"
echo -e "${YELLOW}═══════════════════════════════════════════════════════════${NC}\n"

echo -e "Total Checks: ${TOTAL_CHECKS}"
echo -e "${GREEN}Passed: ${PASSED_CHECKS}${NC}"
echo -e "${RED}Failed: ${FAILED_CHECKS}${NC}"
echo ""

# Calculate percentage
if [ ${TOTAL_CHECKS} -gt 0 ]; then
    PERCENTAGE=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))
    echo -e "Success Rate: ${PERCENTAGE}%"
    echo ""
    
    if [ ${PERCENTAGE} -ge 90 ]; then
        echo -e "${GREEN}✓ System is ready for deployment!${NC}"
        exit 0
    elif [ ${PERCENTAGE} -ge 70 ]; then
        echo -e "${YELLOW}⚠ System is mostly ready, but some issues need attention${NC}"
        exit 1
    else
        echo -e "${RED}✗ System is NOT ready for deployment. Please fix the issues above.${NC}"
        exit 1
    fi
else
    echo -e "${RED}No checks were performed${NC}"
    exit 1
fi

