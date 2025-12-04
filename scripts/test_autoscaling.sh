#!/bin/bash
# Test Cloud Run auto-scaling behavior

set -euo pipefail

# Input validation
if [ $# -lt 4 ]; then
    echo "Usage: $0 <project> <service> <api_url> <auth_token> [region]"
    exit 1
fi

PROJECT_ID=$1
SERVICE_NAME=$2
API_URL=$4
AUTH_TOKEN=$5
REGION=${3:-asia-southeast1}

# Validate inputs
if [[ ! "$PROJECT_ID" =~ ^[a-z0-9-]+$ ]]; then
    echo "❌ Invalid project ID format"
    exit 1
fi

if [[ ! "$SERVICE_NAME" =~ ^[a-z0-9-]+$ ]]; then
    echo "❌ Invalid service name format"
    exit 1
fi

if [[ ! "$API_URL" =~ ^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}.*$ ]]; then
    echo "❌ Invalid API URL format"
    exit 1
fi

if [[ ! "$AUTH_TOKEN" =~ ^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$ ]]; then
    echo "❌ Invalid auth token format"
    exit 1
fi

if [ -z "$PROJECT_ID" ] || [ -z "$SERVICE_NAME" ] || [ -z "$API_URL" ] || [ -z "$AUTH_TOKEN" ]; then
    echo "Usage: $0 \u003cproject\u003e \u003cservice\u003e [region] \u003curl\u003e \u003ctoken\u003e"
    exit 1
fi

echo "=== Auto-Scaling Test ==="
echo "Service: $SERVICE_NAME"
echo "Region: $REGION"

# Function to get instance count
get_instance_count() {
    gcloud run services describe "$SERVICE_NAME" \
        --project="$PROJECT_ID" \
        --region="$REGION" \
        --format="value(status.traffic.latestRevision)" | wc -l
}

# Monitor instances during load ramp
echo -e "\n=== Monitoring Instance Count ==="
for CONCURRENT in 5 10 20 30 40; do
    echo "Testing with $CONCURRENT concurrent users..."

    # Start background load test
    python scripts/load_test_extended.py \
        $API_URL \
        $AUTH_TOKEN \
        --config custom \
        --concurrent-users $CONCURRENT \
        --duration 120 &

    LOAD_PID=$!

    # Monitor instances
    for i in {1..12}; do
        INSTANCES=$(get_instance_count)
        echo "  [$((i*10))s] Instances: $INSTANCES"
        sleep 10
    done

    # Wait for load test to finish
    wait $LOAD_PID

    echo "  Completed $CONCURRENT users test"
    sleep 60  # Wait for scale-down
done

echo -e "\n✅ Auto-scaling test complete"
echo "Check logs for scaling events:"
gcloud logging read "resource.type=cloud_run_revision \
    AND resource.labels.service_name=$SERVICE_NAME \
    AND textPayload=~\"Scaling\"" \
    --limit=20 \
    --project=$PROJECT_ID