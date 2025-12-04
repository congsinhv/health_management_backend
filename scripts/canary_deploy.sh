#!/bin/bash
# Canary deployment with gradual traffic shift

set -euo pipefail

# Input validation
if [ $# -lt 3 ]; then
    echo "Usage: $0 <project> <service> <image> [region]"
    exit 1
fi

PROJECT_ID=$1
SERVICE_NAME=$2
NEW_IMAGE=$3
REGION=${4:-asia-southeast1}

# Validate inputs
if [[ ! "$PROJECT_ID" =~ ^[a-z0-9-]+$ ]]; then
    echo "❌ Invalid project ID format"
    exit 1
fi

if [[ ! "$SERVICE_NAME" =~ ^[a-z0-9-]+$ ]]; then
    echo "❌ Invalid service name format"
    exit 1
fi

if [[ ! "$NEW_IMAGE" =~ ^[a-zA-Z0-9._/-]+:[a-zA-Z0-9._-]+$ ]]; then
    echo "❌ Invalid image format"
    exit 1
fi

if [ -z "$PROJECT_ID" ] || [ -z "$SERVICE_NAME" ] || [ -z "$NEW_IMAGE" ]; then
    echo "Usage: $0 \u003cproject\u003e \u003cservice\u003e \u003cimage\u003e [region]"
    exit 1
fi

echo "=== Canary Deployment ==="
echo "Service: $SERVICE_NAME"
echo "New image: $NEW_IMAGE"

# Deploy new revision without traffic
echo -e "\n[1/5] Deploying new revision (no traffic)..."
REVISION_NAME=$(gcloud run deploy "$SERVICE_NAME" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --image="$NEW_IMAGE" \
    --no-traffic \
    --format="value(status.latestCreatedRevisionName)")

echo "New revision: $REVISION_NAME"

# Get current revision
CURRENT_REVISION=$(gcloud run services describe $SERVICE_NAME \
    --project=$PROJECT_ID \
    --region=$REGION \
    --format="value(status.traffic[0].revisionName)")

echo "Current revision: $CURRENT_REVISION"

# Health check new revision
echo -e "\n[2/5] Health check new revision..."
NEW_REVISION_URL=$(gcloud run revisions describe $REVISION_NAME \
    --project=$PROJECT_ID \
    --region=$REGION \
    --format="value(status.url)")

curl -f $NEW_REVISION_URL/api/v1/qa/health || {
    echo "❌ Health check failed"
    exit 1
}

# Canary: 10% traffic
echo -e "\n[3/5] Routing 10% traffic to new revision..."
gcloud run services update-traffic $SERVICE_NAME \
    --project=$PROJECT_ID \
    --region=$REGION \
    --to-revisions=$REVISION_NAME=10,$CURRENT_REVISION=90

echo "Monitoring canary (30min)..."
sleep 1800

# Check error rate
ERROR_RATE=$(gcloud logging read "resource.type=cloud_run_revision \
    AND resource.labels.revision_name=$REVISION_NAME \
    AND severity=ERROR" \
    --limit=100 \
    --project=$PROJECT_ID \
    --format="value(timestamp)" | wc -l)

if [ $ERROR_RATE -gt 5 ]; then
    echo "❌ High error rate ($ERROR_RATE errors), rolling back..."
    gcloud run services update-traffic $SERVICE_NAME \
        --project=$PROJECT_ID \
        --region=$REGION \
        --to-revisions=$CURRENT_REVISION=100
    exit 1
fi

# 50% traffic
echo -e "\n[4/5] Routing 50% traffic to new revision..."
gcloud run services update-traffic $SERVICE_NAME \
    --project=$PROJECT_ID \
    --region=$REGION \
    --to-revisions=$REVISION_NAME=50,$CURRENT_REVISION=50

sleep 1800  # Monitor 30min

# 100% traffic
echo -e "\n[5/5] Routing 100% traffic to new revision..."
gcloud run services update-traffic $SERVICE_NAME \
    --project=$PROJECT_ID \
    --region=$REGION \
    --to-revisions=$REVISION_NAME=100

echo -e "\n✅ Canary deployment complete"
echo "New revision: $REVISION_NAME"