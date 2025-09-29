pipeline {
    agent any

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
                        set -e  # Exit on any error
                        
                        echo "Authenticating with GCP using service account key..."
                        if ! gcloud auth activate-service-account --key-file="$GCP_KEY_FILE"; then
                            echo "❌ Failed to authenticate with GCP service account"
                            echo "Key file: $GCP_KEY_FILE"
                            echo "Contents check:"
                            ls -la "$GCP_KEY_FILE" || echo "Key file not found"
                            exit 1
                        fi

                        echo "Setting GCP project..."
                        if ! gcloud config set project ${PROJECT_ID}; then
                            echo "❌ Failed to set GCP project: ${PROJECT_ID}"
                            exit 1
                        fi

                        echo "Configuring Docker for Artifact Registry..."
                        if ! gcloud auth configure-docker ${REGISTRY_REGION}-docker.pkg.dev --quiet; then
                            echo "❌ Failed to configure Docker for Artifact Registry"
                            echo "Registry region: ${REGISTRY_REGION}"
                            exit 1
                        fi

                        echo "Verifying authentication..."
                        if ! gcloud auth list; then
                            echo "❌ Failed to list authenticated accounts"
                            exit 1
                        fi
                        
                        if ! gcloud config list; then
                            echo "❌ Failed to list gcloud configuration"
                            exit 1
                        fi
                        
                        echo "✅ GCP authentication setup completed successfully"
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
                echo 'Building Docker image...'
                script {
                    // Build the Docker image
                    sh '''
                        echo "Building Docker image: ${FULL_IMAGE_NAME}"

                        # Build the image with build args
                        docker build \
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
                echo 'Testing Docker image...'
                sh '''
                    # Test that the image can start and respond to health checks
                    echo "Testing Docker image locally..."

                    # Run container in background for testing
                    CONTAINER_ID=$(docker run -d -p 8081:8080 \
                        -e DATABASE_URL="postgresql://test:test@localhost/test" \
                        -e SECRET_KEY="test-secret-key-for-testing-only" \
                        ${FULL_IMAGE_NAME})

                    # Wait for container to start
                    sleep 10

                    # Test health endpoint
                    if curl -f http://localhost:8081/health; then
                        echo "Health check passed"
                    else
                        echo "Health check failed"
                        docker logs $CONTAINER_ID
                        docker stop $CONTAINER_ID
                        exit 1
                    fi

                    # Test root endpoint
                    if curl -f http://localhost:8081/; then
                        echo "Root endpoint test passed"
                    else
                        echo "Root endpoint test failed"
                        docker logs $CONTAINER_ID
                        docker stop $CONTAINER_ID
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
                echo 'Pushing image to Artifact Registry...'
                sh '''
                    echo "Pushing images to Artifact Registry..."

                    # Push versioned image
                    docker push ${FULL_IMAGE_NAME}

                    # Push latest tag
                    docker push ${IMAGE_NAME}:latest

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

                    # Test the deployed service
                    sleep 30  # Wait for service to be ready
                    if curl -f "$SERVICE_URL/health"; then
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
                    # Tag the git commit with the successful deployment
                    git tag -a "deploy-${BUILD_NUMBER}" -m "Deployed build ${BUILD_NUMBER} to Cloud Run"

                    # Tag the Docker image as production
                    docker tag ${FULL_IMAGE_NAME} ${IMAGE_NAME}:production
                    docker push ${IMAGE_NAME}:production

                    echo "Build ${BUILD_NUMBER} successfully deployed and tagged"
                '''
            }
        }
    }

    post {
        always {
            echo 'Cleaning up...'
            sh '''
                # Clean up local Docker images to save space
                docker image prune -f

                # Remove build-specific images but keep latest and production
                docker rmi ${FULL_IMAGE_NAME} || true
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
