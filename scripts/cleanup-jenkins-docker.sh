#!/bin/bash
# Script to clean up Docker resources on Jenkins server
# Run this on your Jenkins server to free up disk space

set -e

echo "=== Docker Disk Usage Before Cleanup ==="
docker system df

echo ""
echo "=== Cleaning up Docker resources ==="

# Remove all stopped containers
echo "Removing stopped containers..."
docker container prune -f

# Remove all dangling images
echo "Removing dangling images..."
docker image prune -f

# Remove all unused images (not just dangling)
echo "Removing unused images..."
docker image prune -af

# Remove all unused volumes
echo "Removing unused volumes..."
docker volume prune -f

# Remove all build cache
echo "Removing build cache..."
docker builder prune -af

echo ""
echo "=== Docker Disk Usage After Cleanup ==="
docker system df

echo ""
echo "=== System Disk Usage ==="
df -h

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "💡 If you still have disk space issues, consider:"
echo "   1. Increasing disk space on your Jenkins server"
echo "   2. Moving Docker's data directory to a larger volume"
echo "   3. Setting up automatic cleanup policies"

