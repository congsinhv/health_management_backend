#!/bin/bash

# Deployment script for Chat AI microservice to Google Cloud Run

set -e

# Configuration
PROJECT_ID="${PROJECT_ID:-vhealth-prod}"
SERVICE_NAME="${SERVICE_NAME:-chat-ai-service}"
REGION="${REGION:-asia-southeast1}"
ENVIRONMENT="${ENVIRONMENT:-prod}"

# Build and push Docker image
echo "Building Docker image..."
docker build -t gcr.io/${PROJECT_ID}/${SERVICE_NAME}:${ENVIRONMENT} .

echo "Pushing Docker image..."
docker push gcr.io/${PROJECT_ID}/${SERVICE_NAME}:${ENVIRONMENT}

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image gcr.io/${PROJECT_ID}/${SERVICE_NAME}:${ENVIRONMENT} \
    --region ${REGION} \
    --platform managed \
    --allow-unauthenticated \
    --memory 4Gi \
    --cpu 2 \
    --timeout 600s \
    --min-instances 0 \
    --max-instances 10 \
    --set-env-vars QA_ENABLED=true \
    --set-env-vars DEBUG=false \
    --set-env-vars LOG_LEVEL=INFO \
    --set-env-vars DEPLOYMENT_ENV=${ENVIRONMENT}

echo "Deployment completed!"
echo "Service URL: https://${SERVICE_NAME}-${REGION}.a.run.app"
echo "Health Check: https://${SERVICE_NAME}-${REGION}.a.run.app/api/v1/qa/health"