#!/bin/bash
#
# Manual Deployment Script for vHealth Backend - Test Environment
# Usage: ./scripts/deploy-test.sh [--skip-build] [--image-tag <tag>]
#
# Options:
#   --skip-build    Skip Docker build and push, use existing image
#   --image-tag     Specify image tag to deploy (required with --skip-build)
#
# Examples:
#   ./scripts/deploy-test.sh                           # Build and deploy
#   ./scripts/deploy-test.sh --skip-build --image-tag manual-20251208-112029  # Deploy existing image
#

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

# Environment
ENV="test"
GCP_PROJECT_ID="vhealth-test"
GCP_REGION="asia-southeast1"

# Artifact Registry
ARTIFACT_REGISTRY_REPO="vhealth-backend-test"
IMAGE_NAME="vhealth-backend"

# Cloud Run
CLOUD_RUN_SERVICE="vhealth-backend-test"
SERVICE_ACCOUNT="vhealth-backend-test@vhealth-test.iam.gserviceaccount.com"
VPC_CONNECTOR="vhealth-vpc-conn-test"

# GCS Buckets
GCS_MODEL_BUCKET="vhealth-test-models"
GCS_PUBLIC_BUCKET="vhealth-test-public"

# Domain
CUSTOM_DOMAIN="test.vhealth.io.vn"
BACKEND_URL="https://api.test.vhealth.io.vn"

# Cloud Tasks
CLOUD_TASKS_QUEUE="vhealth-test-notification-queue"
CLOUD_TASKS_SERVICE_ACCOUNT="cloud-tasks-sa@vhealth-test.iam.gserviceaccount.com"

# Resources
CPU="2"
MEMORY="1.5Gi"
MIN_INSTANCES="1"
MAX_INSTANCES="10"
TIMEOUT="300"
CONCURRENCY="20"

# =============================================================================
# Colors for output
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo ""
    echo "=============================================="
    echo "$1"
    echo "=============================================="
}

# =============================================================================
# Parse Arguments
# =============================================================================

SKIP_BUILD=false
IMAGE_TAG=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --image-tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--skip-build] [--image-tag <tag>]"
            echo ""
            echo "Options:"
            echo "  --skip-build    Skip Docker build and push, use existing image"
            echo "  --image-tag     Specify image tag to deploy (required with --skip-build)"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate arguments
if [ "$SKIP_BUILD" = true ] && [ -z "$IMAGE_TAG" ]; then
    log_error "--image-tag is required when using --skip-build"
    exit 1
fi

# Generate image tag if not provided
if [ -z "$IMAGE_TAG" ]; then
    IMAGE_TAG="manual-$(date +%Y%m%d-%H%M%S)"
fi

# Full image path
IMAGE_FULL="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/${IMAGE_NAME}:${IMAGE_TAG}"

# Revision suffix
REVISION_SUFFIX="manual-$(date +%Y%m%d-%H%M%S)"

# =============================================================================
# Pre-flight Checks
# =============================================================================

print_header "Pre-flight Checks"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    log_error "gcloud CLI is not installed"
    exit 1
fi
log_success "gcloud CLI found"

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed"
    exit 1
fi
log_success "Docker found"

# Check gcloud authentication
CURRENT_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null || echo "")
if [ -z "$CURRENT_ACCOUNT" ]; then
    log_error "Not authenticated with gcloud. Run: gcloud auth login"
    exit 1
fi
log_success "Authenticated as: $CURRENT_ACCOUNT"

# Check current project
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [ "$CURRENT_PROJECT" != "$GCP_PROJECT_ID" ]; then
    log_warning "Current project is '$CURRENT_PROJECT', switching to '$GCP_PROJECT_ID'"
    gcloud config set project "$GCP_PROJECT_ID"
fi
log_success "Project: $GCP_PROJECT_ID"

# =============================================================================
# Print Configuration
# =============================================================================

print_header "Deployment Configuration"

echo "Environment:        $ENV"
echo "Project:            $GCP_PROJECT_ID"
echo "Region:             $GCP_REGION"
echo "Service:            $CLOUD_RUN_SERVICE"
echo "Image Tag:          $IMAGE_TAG"
echo "Image:              $IMAGE_FULL"
echo "Revision:           $REVISION_SUFFIX"
echo "Skip Build:         $SKIP_BUILD"
echo "Domain:             $CUSTOM_DOMAIN"
echo "Backend URL:        $BACKEND_URL"
echo ""

# Confirm deployment
read -p "Proceed with deployment? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warning "Deployment cancelled"
    exit 0
fi

# =============================================================================
# Build and Push Docker Image
# =============================================================================

if [ "$SKIP_BUILD" = false ]; then
    print_header "Building Docker Image"

    # Configure Docker for Artifact Registry
    log_info "Configuring Docker authentication..."
    gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet

    # Build the image
    log_info "Building image: $IMAGE_FULL"
    docker build \
        --platform linux/amd64 \
        -t "$IMAGE_FULL" \
        -f Dockerfile \
        .

    log_success "Image built successfully"

    print_header "Pushing Docker Image"

    log_info "Pushing image to Artifact Registry..."
    docker push "$IMAGE_FULL"

    log_success "Image pushed successfully"
else
    log_info "Skipping build, using existing image: $IMAGE_FULL"
    
    # Verify image exists
    print_header "Verifying Image Exists"
    if gcloud artifacts docker images describe "$IMAGE_FULL" --quiet &>/dev/null; then
        log_success "Image found in Artifact Registry"
    else
        log_error "Image not found: $IMAGE_FULL"
        exit 1
    fi
fi

# =============================================================================
# Deploy to Cloud Run
# =============================================================================

print_header "Deploying to Cloud Run"

log_info "Deploying service: $CLOUD_RUN_SERVICE"
log_info "Region: $GCP_REGION"
log_info "Revision: $REVISION_SUFFIX"

gcloud run deploy "$CLOUD_RUN_SERVICE" \
    --image "$IMAGE_FULL" \
    --platform managed \
    --region "$GCP_REGION" \
    --service-account "$SERVICE_ACCOUNT" \
    --vpc-connector "$VPC_CONNECTOR" \
    --vpc-egress private-ranges-only \
    --set-env-vars "DEBUG=True" \
    --set-env-vars "LOG_LEVEL=DEBUG" \
    --set-env-vars "ENVIRONMENT=$ENV" \
    --set-env-vars "QA_ENABLED=true" \
    --set-env-vars "GCP_PROJECT_ID=$GCP_PROJECT_ID" \
    --set-env-vars "GCP_MODEL_BUCKET=$GCS_MODEL_BUCKET" \
    --set-env-vars "GCP_MODEL_BLOB_PATH=models/vietnamese-sbert/" \
    --set-env-vars "GCP_DATA_BLOB_PATH=data/" \
    --set-env-vars "MODEL_AUTO_DOWNLOAD=true" \
    --set-env-vars "ENABLE_REDIS_CACHE=true" \
    --set-env-vars "CLOUD_TASKS_ENABLED=true" \
    --set-env-vars "CLOUD_TASKS_QUEUE=$CLOUD_TASKS_QUEUE" \
    --set-env-vars "CLOUD_TASKS_LOCATION=$GCP_REGION" \
    --set-env-vars "CLOUD_TASKS_SERVICE_ACCOUNT=$CLOUD_TASKS_SERVICE_ACCOUNT" \
    --set-env-vars "FCM_ENABLED=true" \
    --set-env-vars "CUSTOM_DOMAIN=$CUSTOM_DOMAIN" \
    --set-env-vars "BACKEND_URL=$BACKEND_URL" \
    --set-env-vars "^@^CORS_ORIGINS=https://$CUSTOM_DOMAIN,https://api.$CUSTOM_DOMAIN" \
    --set-env-vars "WEBUI_URL=https://$CUSTOM_DOMAIN" \
    --set-env-vars "GCP_PUBLIC_BUCKET=$GCS_PUBLIC_BUCKET" \
    --set-secrets "DATABASE_URL=vhealth-$ENV-database-url:latest" \
    --set-secrets "SECRET_KEY=vhealth-$ENV-secret-key:latest" \
    --set-secrets "OPENAI_API_KEY=vhealth-$ENV-openai-api-key:latest" \
    --set-secrets "GOOGLE_CLIENT_ID=vhealth-$ENV-google-client-id:latest" \
    --set-secrets "GOOGLE_CLIENT_SECRET=vhealth-$ENV-google-client-secret:latest" \
    --set-secrets "MAIL_USERNAME=vhealth-$ENV-mail-username:latest" \
    --set-secrets "MAIL_PASSWORD=vhealth-$ENV-mail-password:latest" \
    --set-secrets "MAIL_FROM=vhealth-$ENV-mail-from:latest" \
    --set-secrets "MAIL_SERVER=vhealth-$ENV-mail-server:latest" \
    --set-secrets "REDIS_HOST=vhealth-$ENV-redis-host:latest" \
    --set-secrets "REDIS_PORT=vhealth-$ENV-redis-port:latest" \
    --set-secrets "REDIS_PASSWORD=vhealth-$ENV-redis-auth-secret:latest" \
    --set-secrets "FCM_CREDENTIALS_JSON=vhealth-$ENV-firebase-fcm-credentials:latest" \
    --cpu "$CPU" \
    --memory "$MEMORY" \
    --min-instances "$MIN_INSTANCES" \
    --max-instances "$MAX_INSTANCES" \
    --timeout "$TIMEOUT" \
    --concurrency "$CONCURRENCY" \
    --allow-unauthenticated \
    --revision-suffix "$REVISION_SUFFIX" \
    --quiet

log_success "Deployment completed"

# =============================================================================
# Verify Deployment
# =============================================================================

print_header "Verifying Deployment"

# Get service URL
SERVICE_URL=$(gcloud run services describe "$CLOUD_RUN_SERVICE" \
    --region "$GCP_REGION" \
    --format "value(status.url)")

log_info "Service URL: $SERVICE_URL"

# Health check
log_info "Running health check..."
sleep 5  # Wait for service to be ready

HEALTH_RESPONSE=$(curl -s "${SERVICE_URL}/health" || echo '{"status":"error"}')
HEALTH_STATUS=$(echo "$HEALTH_RESPONSE" | jq -r '.status' 2>/dev/null || echo "error")

if [ "$HEALTH_STATUS" = "healthy" ]; then
    log_success "Health check passed"
    echo "$HEALTH_RESPONSE" | jq .
else
    log_warning "Health check returned: $HEALTH_STATUS"
    echo "$HEALTH_RESPONSE"
fi

# =============================================================================
# Summary
# =============================================================================

print_header "Deployment Summary"

echo -e "Environment:     ${GREEN}$ENV${NC}"
echo -e "Service:         ${GREEN}$CLOUD_RUN_SERVICE${NC}"
echo -e "Revision:        ${GREEN}$REVISION_SUFFIX${NC}"
echo -e "Image Tag:       ${GREEN}$IMAGE_TAG${NC}"
echo -e "Service URL:     ${GREEN}$SERVICE_URL${NC}"
echo -e "Health Status:   ${GREEN}$HEALTH_STATUS${NC}"
echo ""
echo "Useful commands:"
echo "  # View logs"
echo "  gcloud run services logs read $CLOUD_RUN_SERVICE --region $GCP_REGION --limit 50"
echo ""
echo "  # List revisions"
echo "  gcloud run revisions list --service $CLOUD_RUN_SERVICE --region $GCP_REGION"
echo ""
echo "  # Rollback to previous revision"
echo "  gcloud run services update-traffic $CLOUD_RUN_SERVICE --region $GCP_REGION --to-revisions <revision-name>=100"
echo ""

log_success "Deployment to test environment completed!"

