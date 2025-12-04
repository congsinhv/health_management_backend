#!/bin/bash
# Validate Docker build size and integrity

set -euo pipefail

# Input validation
if [ $# -gt 1 ]; then
    echo "Usage: $0 [image-tag]"
    exit 1
fi

IMAGE_TAG=${1:-latest}
# Sanitize image tag - only allow alphanumeric, dash, underscore, dot
if [[ ! "$IMAGE_TAG" =~ ^[a-zA-Z0-9._-]+$ ]]; then
    echo "❌ Invalid image tag format. Only alphanumeric, dash, underscore, dot allowed."
    exit 1
fi

IMAGE_NAME="vhealth-backend:${IMAGE_TAG}"
MAX_SIZE_MB=1000  # 1GB max

echo "=== Building Docker Image ==="
docker build -t "$IMAGE_NAME" .

echo -e "\n=== Checking Image Size ==="
SIZE_BYTES=$(docker image inspect "$IMAGE_NAME" --format='{{.Size}}')
SIZE_MB=$((SIZE_BYTES / 1024 / 1024))

echo "Image size: ${SIZE_MB}MB"

if [ $SIZE_MB -gt $MAX_SIZE_MB ]; then
    echo "❌ Image too large: ${SIZE_MB}MB > ${MAX_SIZE_MB}MB"
    exit 1
fi

echo "✅ Image size acceptable: ${SIZE_MB}MB"

echo -e "\n=== Testing Image Startup ==="
CONTAINER_ID=$(docker run -d \
    -e QA_ENABLED=false \
    -e DATABASE_URL=postgresql://test:test@localhost:5432/test \
    "$IMAGE_NAME")

# Wait for startup
sleep 5

# Check if running
if docker ps | grep -q "$CONTAINER_ID"; then
    echo "✅ Container started successfully"
    docker stop "$CONTAINER_ID" > /dev/null
    docker rm "$CONTAINER_ID" > /dev/null
else
    echo "❌ Container failed to start"
    docker logs "$CONTAINER_ID"
    docker rm "$CONTAINER_ID" > /dev/null
    exit 1
fi

echo -e "\n=== Validating Dependencies ==="
docker run --rm "$IMAGE_NAME" python -c "
import sys
try:
    import fastapi
    import optimum.onnxruntime
    import msgpack_numpy
    import redis
    print('✅ All dependencies installed')
except ImportError as e:
    print(f'❌ Missing dependency: {e}')
    sys.exit(1)
"

echo -e "\n=== Build Validation Complete ==="