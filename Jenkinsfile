pipeline {
    agent {
        docker {
            image 'google/cloud-sdk:alpine'
            args '-u root:root --network host'
        }
    }

    environment {
        // GCP Configuration
        PROJECT_ID = 'health-management-app-473504'  // Replace with your GCP project ID
        REGION = 'asia-southeast1'              // Use free tier region
        SERVICE_NAME = 'health-management-api'

        // Artifact Registry Configuration
        REGISTRY_REGION = 'asia-southeast1'     // Use same region as Cloud Run
        REGISTRY_NAME = 'health-management'
        IMAGE_NAME = "${REGISTRY_REGION}-docker.pkg.dev/${PROJECT_ID}/${REGISTRY_NAME}/${SERVICE_NAME}"

        // Cloud Run Configuration
        CLOUD_RUN_REGION = 'asia-southeast1'
        MIN_INSTANCES = '0'                 // Scale to zero for cost optimization
        MAX_INSTANCES = '10'
        MEMORY = '512Mi'                    // Free tier optimized
        CPU = '1'
        CONCURRENCY = '80'

        // Build Configuration
        IMAGE_TAG = "${BUILD_NUMBER}"
        FULL_IMAGE_NAME = "${IMAGE_NAME}:${IMAGE_TAG}"
    }

    stages {
        stage('Checkout') {
            steps {
                echo 'Checking out source code...'
                checkout scm

                // Display build information
                sh '''
                    echo "=== Build Information ==="
                    echo "Build Number: ${BUILD_NUMBER}"
                    echo "Project ID: ${PROJECT_ID}"
                    echo "Image: ${FULL_IMAGE_NAME}"
                    echo "Service: ${SERVICE_NAME}"
                    echo "========================"
                '''
            }
        }

        stage('Setup GCP Authentication') {
            steps {
                echo 'Setting up GCP authentication...'
                withCredentials([file(credentialsId: 'gcp-key-json', variable: 'GCP_KEY_FILE')]) {
                    sh '''
                        echo "Authenticating with GCP..."
                        gcloud auth activate-service-account --key-file="$GCP_KEY_FILE"
                        
                        echo "Setting GCP project to ${PROJECT_ID}..."
                        gcloud config set project ${PROJECT_ID}
                        
                        echo "Configuring Docker authentication..."
                        gcloud auth configure-docker ${REGISTRY_REGION}-docker.pkg.dev --quiet
                        
                        echo "=== Authentication Status ==="
                        gcloud auth list
                        gcloud config list project
                        echo "============================="
                    '''
                }
            }
        }

        stage('Create Artifact Registry') {
            steps {
                echo 'Ensuring Artifact Registry exists...'
                sh '''
                    # Check if repository exists, create if not
                    if ! gcloud artifacts repositories describe ${REGISTRY_NAME} \
                        --location=${REGISTRY_REGION} \
                        --format="value(name)" 2>/dev/null; then

                        echo "Creating Artifact Registry repository..."
                        gcloud artifacts repositories create ${REGISTRY_NAME} \
                            --repository-format=docker \
                            --location=${REGISTRY_REGION} \
                            --description="Docker registry for Health Management API"
                    else
                        echo "Artifact Registry repository already exists"
                    fi
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                echo 'Building Docker image with caching...'
                script {
                    // Build the Docker image with layer caching
                    sh '''
                        echo "Building Docker image: ${FULL_IMAGE_NAME}"
                        
                        # Install Docker CLI in the container if not present
                        if ! command -v docker >/dev/null 2>&1; then
                            echo "Installing Docker CLI..."
                            apk add --no-cache docker-cli
                        fi

                        # Pull latest image for layer caching (ignore failures)
                        docker pull ${IMAGE_NAME}:latest || echo "No previous image found for caching"

                        # Build the image with build args and cache optimization
                        docker build \
                            --cache-from=${IMAGE_NAME}:latest \
                            --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
                            --build-arg VCS_REF=$(git rev-parse --short HEAD) \
                            --build-arg BUILD_NUMBER=${BUILD_NUMBER} \
                            -t ${FULL_IMAGE_NAME} \
                            -t ${IMAGE_NAME}:latest \
                            .

                        # Verify image was built
                        docker images | grep ${SERVICE_NAME}
                    '''
                }
            }
        }

        stage('Test Docker Image') {
            steps {
                echo 'Testing Docker image with intelligent polling...'
                sh '''
                    # Test that the image can start and respond to health checks
                    echo "Testing Docker image locally..."

                    # Run container in background for testing
                    CONTAINER_ID=$(docker run -d -p 8081:8080 \
                        -e DATABASE_URL="postgresql://test:test@localhost/test" \
                        -e SECRET_KEY="test-secret-key-for-testing-only" \
                        ${FULL_IMAGE_NAME})

                    # Function to wait for service with timeout
                    wait_for_service() {
                        local url=$1
                        local timeout=30
                        local counter=0
                        
                        echo "Waiting for service at $url..."
                        while [ $counter -lt $timeout ]; do
                            if curl -f --connect-timeout 2 --max-time 5 "$url" >/dev/null 2>&1; then
                                echo "Service is ready after ${counter} seconds"
                                return 0
                            fi
                            sleep 1
                            counter=$((counter + 1))
                        done
                        echo "Service failed to start within $timeout seconds"
                        return 1
                    }

                    # Wait for container to start and test endpoints
                    if wait_for_service "http://localhost:8081/health"; then
                        echo "Health check passed"
                    else
                        echo "Health check failed"
                        docker logs $CONTAINER_ID
                        docker stop $CONTAINER_ID
                        docker rm $CONTAINER_ID
                        exit 1
                    fi

                    # Test root endpoint (should be fast now)
                    if curl -f --connect-timeout 2 --max-time 5 http://localhost:8081/; then
                        echo "Root endpoint test passed"
                    else
                        echo "Root endpoint test failed"
                        docker logs $CONTAINER_ID
                        docker stop $CONTAINER_ID
                        docker rm $CONTAINER_ID
                        exit 1
                    fi

                    # Clean up
                    docker stop $CONTAINER_ID
                    docker rm $CONTAINER_ID
                '''
            }
        }

        stage('Push to Artifact Registry') {
            steps {
                echo 'Pushing image to Artifact Registry in parallel...'
                sh '''
                    echo "Pushing images to Artifact Registry..."

                    # Push versioned image and latest tag in parallel
                    docker push ${FULL_IMAGE_NAME} &
                    PUSH1_PID=$!
                    
                    docker push ${IMAGE_NAME}:latest &
                    PUSH2_PID=$!

                    # Wait for both pushes to complete
                    echo "Waiting for parallel pushes to complete..."
                    wait $PUSH1_PID
                    PUSH1_STATUS=$?
                    wait $PUSH2_PID  
                    PUSH2_STATUS=$?

                    if [ $PUSH1_STATUS -ne 0 ] || [ $PUSH2_STATUS -ne 0 ]; then
                        echo "One or more pushes failed"
                        exit 1
                    fi

                    echo "Images pushed successfully"
                '''
            }
        }

        stage('Deploy to Cloud Run') {
            steps {
                echo 'Deploying to Cloud Run...'
                sh '''
                    echo "Deploying ${SERVICE_NAME} to Cloud Run..."

                    # Deploy to Cloud Run with optimized settings for free tier
                    gcloud run deploy ${SERVICE_NAME} \
                        --image=${FULL_IMAGE_NAME} \
                        --region=${CLOUD_RUN_REGION} \
                        --platform=managed \
                        --allow-unauthenticated \
                        --memory=${MEMORY} \
                        --cpu=${CPU} \
                        --concurrency=${CONCURRENCY} \
                        --min-instances=${MIN_INSTANCES} \
                        --max-instances=${MAX_INSTANCES} \
                        --timeout=300 \
                        --set-env-vars="PORT=8080" \
                        --set-secrets="DATABASE_URL=vhealth-database-url:latest,SECRET_KEY=vhealth-jwt-secret-key:latest" \
                        --port=8080 \
                        --quiet

                    # Get the service URL
                    SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
                        --region=${CLOUD_RUN_REGION} \
                        --format="value(status.url)")

                    echo "=== Deployment Successful ==="
                    echo "Service URL: $SERVICE_URL"
                    echo "Image: ${FULL_IMAGE_NAME}"
                    echo "Build: ${BUILD_NUMBER}"
                    echo "=========================="

                    # Function to wait for Cloud Run service with intelligent polling
                    wait_for_cloud_run() {
                        local url=$1
                        local timeout=120
                        local counter=0
                        
                        echo "Waiting for Cloud Run service at $url..."
                        while [ $counter -lt $timeout ]; do
                            if curl -f --connect-timeout 5 --max-time 10 "$url/health" >/dev/null 2>&1; then
                                echo "Cloud Run service is ready after ${counter} seconds"
                                return 0
                            fi
                            sleep 2
                            counter=$((counter + 2))
                            if [ $((counter % 20)) -eq 0 ]; then
                                echo "Still waiting... (${counter}s elapsed)"
                            fi
                        done
                        echo "Cloud Run service failed to start within $timeout seconds"
                        return 1
                    }

                    # Test the deployed service with intelligent polling
                    if wait_for_cloud_run "$SERVICE_URL"; then
                        echo "Deployment health check passed"
                    else
                        echo "Deployment health check failed"
                        exit 1
                    fi
                '''
            }
        }

        stage('Tag and Promote') {
            steps {
                echo 'Tagging successful deployment...'
                sh '''
                    # Tag the git commit with the successful deployment (background)
                    git tag -a "deploy-${BUILD_NUMBER}" -m "Deployed build ${BUILD_NUMBER} to Cloud Run" &
                    GIT_TAG_PID=$!

                    # Tag and push the Docker image as production (background)
                    docker tag ${FULL_IMAGE_NAME} ${IMAGE_NAME}:production
                    docker push ${IMAGE_NAME}:production &
                    DOCKER_PUSH_PID=$!

                    # Wait for git tagging to complete
                    wait $GIT_TAG_PID

                    # Wait for docker push to complete
                    wait $DOCKER_PUSH_PID
                    if [ $? -ne 0 ]; then
                        echo "Production image push failed"
                        exit 1
                    fi

                    echo "Build ${BUILD_NUMBER} successfully deployed and tagged"
                '''
            }
        }
    }

    post {
        always {
            echo 'Cleaning up...'
            sh '''
                # Clean up local Docker images to save space (background)
                docker image prune -f &
                PRUNE_PID=$!

                # Remove build-specific images but keep latest and production (background)
                docker rmi ${FULL_IMAGE_NAME} &
                RMI_PID=$!

                # Wait for cleanup operations (don't fail if they error)
                wait $PRUNE_PID || true
                wait $RMI_PID || true

                echo "Cleanup completed"
            '''
        }

        success {
            echo 'Pipeline completed successfully!'
            script {
                // Get service URL for notification
                def serviceUrl = sh(
                    script: "gcloud run services describe ${SERVICE_NAME} --region=${CLOUD_RUN_REGION} --format='value(status.url)'",
                    returnStdout: true
                ).trim()

                echo "✅ Deployment successful! Service available at: ${serviceUrl}"
            }
        }

        failure {
            echo '❌ Pipeline failed!'
            sh '''
                # Collect logs for debugging
                echo "=== Container Logs ==="
                docker logs $(docker ps -a -q --filter "ancestor=${FULL_IMAGE_NAME}") || true

                echo "=== Cloud Run Logs ==="
                gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}" \
                    --limit=50 --format="table(timestamp,severity,textPayload)" || true
            '''
        }

        unstable {
            echo '⚠️ Pipeline completed with warnings'
        }
    }
}
