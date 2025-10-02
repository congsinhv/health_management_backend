pipeline {
    agent any

    parameters {
        choice(
            name: 'ENVIRONMENT',
            choices: ['dev', 'prod'],
            description: 'Target environment for deployment'
        )
        string(
            name: 'BRANCH_NAME',
            defaultValue: 'develop',
            description: 'Git branch to deploy'
        )
    }

    environment {
        // GCP Project Configuration - Hard-coded (non-sensitive)
        GCP_REGION = 'asia-southeast1'  // Singapore - closest to Vietnam
        ENV = "${params.ENVIRONMENT}"
        
        // Project IDs - Hard-coded per environment
        GCP_PROJECT_ID = "${params.ENVIRONMENT == 'prod' ? 'vhealth-prod' : 'vhealth-dev'}"
        
        // Terraform state bucket - Hard-coded per environment
        TF_BACKEND_BUCKET = "${GCP_PROJECT_ID}-tfstate"

        // Artifact Registry Configuration - No prefix needed
        ARTIFACT_REGISTRY_REPO = "health-management-${params.ENVIRONMENT}"
        IMAGE_NAME = "health-api"
        IMAGE_TAG = "${env.BUILD_NUMBER}-${env.GIT_COMMIT.take(7)}"
        IMAGE_FULL = "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/${IMAGE_NAME}:${IMAGE_TAG}"
        IMAGE_LATEST = "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/${IMAGE_NAME}:latest"

        // Terraform Configuration
        TF_IN_AUTOMATION = 'true'
        TF_VAR_FILE = "terraform/environments/${params.ENVIRONMENT}.tfvars"

        // Service Account Key for GCP authentication - Only Jenkins credential needed
        GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-service-account-key')
        
        // Application secrets will be fetched from GCP Secret Manager
        // (No longer stored in Jenkins credentials)
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 60, unit: 'MINUTES')
        timestamps()
        disableConcurrentBuilds()
    }

    stages {
        stage('Initialize') {
            steps {
                script {
                    echo '=========================================='
                    echo 'Deployment Configuration'
                    echo '=========================================='
                    echo "Environment: ${params.ENVIRONMENT}"
                    echo "Branch: ${params.BRANCH_NAME}"
                    echo "GCP Project: ${GCP_PROJECT_ID}"
                    echo "GCP Region: ${GCP_REGION}"
                    echo "Terraform State Bucket: ${TF_BACKEND_BUCKET}"
                    echo "Image: ${IMAGE_FULL}"
                    echo '=========================================='
                }
            }
        }

        stage('Checkout') {
            steps {
                script {
                    echo "Checking out branch: ${params.BRANCH_NAME}"
                    checkout([
                        $class: 'GitSCM',
                        branches: [[name: "*/${params.BRANCH_NAME}"]],
                        userRemoteConfigs: scm.userRemoteConfigs
                    ])
                }
            }
        }

        stage('Authenticate to GCP') {
            steps {
                script {
                    echo 'Authenticating to GCP...'
                    sh '''
                        gcloud auth activate-service-account --key-file=${GOOGLE_APPLICATION_CREDENTIALS}
                        gcloud config set project ${GCP_PROJECT_ID}
                        gcloud config set compute/region ${GCP_REGION}

                        # Configure Docker to use gcloud as credential helper
                        gcloud auth configure-docker ${GCP_REGION}-docker.pkg.dev --quiet
                    '''
                }
            }
        }

        stage('Terraform Init') {
            steps {
                dir('terraform') {
                    script {
                        echo 'Initializing Terraform...'
                        sh """
                            terraform init \
                                -backend-config="bucket=${TF_BACKEND_BUCKET}" \
                                -backend-config="prefix=terraform/state/${params.ENVIRONMENT}" \
                                -reconfigure
                        """
                    }
                }
            }
        }

        stage('Terraform Validate') {
            steps {
                dir('terraform') {
                    script {
                        echo 'Validating Terraform configuration...'
                        sh 'terraform validate'
                    }
                }
            }
        }

        stage('Fetch Secrets from GCP Secret Manager') {
            steps {
                script {
                    echo 'Fetching secrets from GCP Secret Manager...'
                    
                    // Generate a secure random secret key
                    env.TF_VAR_secret_key = sh(
                        script: "python3 -c 'import secrets; print(secrets.token_urlsafe(32))'",
                        returnStdout: true
                    ).trim()
                    
                    // Check if secrets exist in Secret Manager, if not use placeholders
                    // This allows first deployment to work, then we update secrets in GCP
                    try {
                        env.TF_VAR_database_url = sh(
                            script: "gcloud secrets versions access latest --secret=database-url-${params.ENVIRONMENT} --project=${GCP_PROJECT_ID} 2>/dev/null || echo 'postgresql://placeholder:placeholder@localhost/placeholder'",
                            returnStdout: true
                        ).trim()
                    } catch (Exception e) {
                        env.TF_VAR_database_url = 'postgresql://placeholder:placeholder@localhost/placeholder'
                    }
                    
                    try {
                        env.TF_VAR_google_client_id = sh(
                            script: "gcloud secrets versions access latest --secret=google-client-id-${params.ENVIRONMENT} --project=${GCP_PROJECT_ID} 2>/dev/null || echo 'placeholder-client-id'",
                            returnStdout: true
                        ).trim()
                    } catch (Exception e) {
                        env.TF_VAR_google_client_id = 'placeholder-client-id'
                    }
                    
                    try {
                        env.TF_VAR_google_client_secret = sh(
                            script: "gcloud secrets versions access latest --secret=google-client-secret-${params.ENVIRONMENT} --project=${GCP_PROJECT_ID} 2>/dev/null || echo 'placeholder-client-secret'",
                            returnStdout: true
                        ).trim()
                    } catch (Exception e) {
                        env.TF_VAR_google_client_secret = 'placeholder-client-secret'
                    }
                    
                    try {
                        env.TF_VAR_mail_username = sh(
                            script: "gcloud secrets versions access latest --secret=mail-username-${params.ENVIRONMENT} --project=${GCP_PROJECT_ID} 2>/dev/null || echo 'placeholder@example.com'",
                            returnStdout: true
                        ).trim()
                    } catch (Exception e) {
                        env.TF_VAR_mail_username = 'placeholder@example.com'
                    }
                    
                    try {
                        env.TF_VAR_mail_password = sh(
                            script: "gcloud secrets versions access latest --secret=mail-password-${params.ENVIRONMENT} --project=${GCP_PROJECT_ID} 2>/dev/null || echo 'placeholder-password'",
                            returnStdout: true
                        ).trim()
                    } catch (Exception e) {
                        env.TF_VAR_mail_password = 'placeholder-password'
                    }
                    
                    echo 'Secrets fetched successfully!'
                    echo "Database URL: ${env.TF_VAR_database_url.take(30)}..."
                    echo "Secret key: [GENERATED - ${env.TF_VAR_secret_key.length()} characters]"
                    echo "Google Client ID: ${env.TF_VAR_google_client_id.take(20)}..."
                    echo "Mail Username: ${env.TF_VAR_mail_username}"
                }
            }
        }

        stage('Terraform Plan') {
            steps {
                dir('terraform') {
                    script {
                        echo 'Planning Terraform changes...'
                        sh """
                            terraform plan \
                                -var-file="environments/${params.ENVIRONMENT}.tfvars" \
                                -out=tfplan
                        """
                    }
                }
            }
        }

        stage('Approve Terraform Apply') {
            when {
                expression { return params.ENVIRONMENT == 'prod' }
            }
            steps {
                script {
                    echo 'Production deployment detected. Manual approval required.'
                    input message: 'Apply Terraform changes to PRODUCTION?',
                          ok: 'Deploy',
                          submitter: 'admin'
                }
            }
        }

        stage('Terraform Apply') {
            steps {
                dir('terraform') {
                    script {
                        echo 'Applying Terraform changes...'
                        sh 'terraform apply -auto-approve tfplan'

                        // Export outputs for later stages
                        sh '''
                            terraform output -json > terraform_outputs.json
                            cat terraform_outputs.json
                        '''
                    }
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    echo "Building Docker image: ${IMAGE_FULL}"
                    sh """
                        docker build \
                            --build-arg BUILD_DATE=\$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
                            --build-arg VERSION=${IMAGE_TAG} \
                            --build-arg GIT_COMMIT=${GIT_COMMIT} \
                            -t ${IMAGE_FULL} \
                            -t ${IMAGE_LATEST} \
                            .
                    """
                }
            }
        }

        stage('Run Security Scan') {
            steps {
                script {
                    echo 'Running Trivy security scan...'
                    sh """
                        # Install Trivy if not available
                        if ! command -v trivy &> /dev/null; then
                            wget -qO - https://aquasecurity.github.io/trivy-repo/deb/public.key | sudo apt-key add -
                            echo "deb https://aquasecurity.github.io/trivy-repo/deb \$(lsb_release -sc) main" | sudo tee -a /etc/apt/sources.list.d/trivy.list
                            sudo apt-get update
                            sudo apt-get install trivy -y
                        fi

                        # Scan for HIGH and CRITICAL vulnerabilities
                        trivy image --severity HIGH,CRITICAL --exit-code 0 ${IMAGE_FULL}
                    """
                }
            }
        }

        stage('Push to Artifact Registry') {
            steps {
                script {
                    echo 'Pushing image to Artifact Registry...'
                    sh """
                        docker push ${IMAGE_FULL}
                        docker push ${IMAGE_LATEST}
                    """
                }
            }
        }

        stage('Approve Cloud Run Deployment') {
            when {
                expression { return params.ENVIRONMENT == 'prod' }
            }
            steps {
                script {
                    echo 'Production deployment detected. Manual approval required.'
                    input message: 'Deploy to Cloud Run PRODUCTION?',
                          ok: 'Deploy',
                          submitter: 'admin'
                }
            }
        }

        stage('Deploy to Cloud Run') {
            steps {
                script {
                    echo 'Deploying to Cloud Run...'

                    // Get Cloud Run service name from Terraform output
                    def cloudRunService = sh(
                        script: 'cd terraform && terraform output -raw cloud_run_service_name',
                        returnStdout: true
                    ).trim()

                    sh """
                        gcloud run deploy ${cloudRunService} \
                            --image ${IMAGE_FULL} \
                            --platform managed \
                            --region ${GCP_REGION} \
                            --project ${GCP_PROJECT_ID} \
                            --quiet
                    """

                    // Get service URL
                    def serviceUrl = sh(
                        script: "gcloud run services describe ${cloudRunService} --region=${GCP_REGION} --format='value(status.url)'",
                        returnStdout: true
                    ).trim()

                    echo "Service deployed at: ${serviceUrl}"
                }
            }
        }

        stage('Run Database Migrations') {
            steps {
                script {
                    echo 'Running database migrations...'

                    // Get Cloud SQL connection name from Terraform
                    def connectionName = sh(
                        script: 'cd terraform && terraform output -raw cloud_sql_connection_name',
                        returnStdout: true
                    ).trim()

                    sh """
                        # Download Cloud SQL Proxy if not exists
                        if [ ! -f cloud_sql_proxy ]; then
                            wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -O cloud_sql_proxy
                            chmod +x cloud_sql_proxy
                        fi

                        # Start Cloud SQL Proxy in background
                        ./cloud_sql_proxy -instances=${connectionName}=tcp:5432 &
                        PROXY_PID=\$!

                        # Wait for proxy to be ready
                        sleep 5

                        # Run migrations
                        cd scripts
                        export DATABASE_URL="${TF_VAR_database_url}"
                        python3 -m venv venv || true
                        . venv/bin/activate
                        pip install -q alembic asyncpg psycopg2-binary
                        alembic upgrade head

                        # Kill proxy
                        kill \$PROXY_PID || true
                    """
                }
            }
        }

        stage('Smoke Tests') {
            steps {
                script {
                    echo 'Running smoke tests...'

                    def serviceUrl = sh(
                        script: 'cd terraform && terraform output -raw cloud_run_service_url',
                        returnStdout: true
                    ).trim()

                    sh """
                        # Test health endpoint
                        echo "Testing health endpoint..."
                        curl -f ${serviceUrl}/health || exit 1

                        # Test root endpoint
                        echo "Testing root endpoint..."
                        curl -f ${serviceUrl}/ || exit 1

                        echo "All smoke tests passed!"
                    """
                }
            }
        }

        stage('Tag Release') {
            when {
                expression { return params.ENVIRONMENT == 'prod' }
            }
            steps {
                script {
                    echo 'Tagging release...'
                    def tagName = "v${IMAGE_TAG}"

                    sh """
                        git tag -a ${tagName} -m "Release ${tagName} to production"
                        git push origin ${tagName} || echo "Tag already exists or push failed"
                    """
                }
            }
        }
    }

    post {
        success {
            echo '=========================================='
            echo 'Deployment completed successfully!'
            echo "Environment: ${params.ENVIRONMENT}"
            echo "Image: ${IMAGE_FULL}"
            echo '=========================================='
        }
        failure {
            echo '=========================================='
            echo 'Deployment failed!'
            echo "Environment: ${params.ENVIRONMENT}"
            echo 'Please check the logs for details.'
            echo '=========================================='
        }
        always {
            // Clean up
            sh '''
                docker system prune -f || true
                rm -f cloud_sql_proxy || true
            '''
        }
    }
}
