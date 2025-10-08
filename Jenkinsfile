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
        GCP_REGION = 'asia-southeast1'
        ENV = "${params.ENVIRONMENT}"
        GCP_PROJECT_ID = "${params.ENVIRONMENT == 'prod' ? 'vhealth-prod' : 'vhealth-dev'}"
        TF_BACKEND_BUCKET = "${GCP_PROJECT_ID}-backend-tfstate"

        ARTIFACT_REGISTRY_REPO = "vhealth-backend-${params.ENVIRONMENT}"
        IMAGE_NAME = "vhealth-backend"
        IMAGE_TAG = "${env.BUILD_NUMBER}-${env.GIT_COMMIT.take(7)}"
        IMAGE_FULL = "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/${IMAGE_NAME}:${IMAGE_TAG}"
        IMAGE_LATEST = "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/${IMAGE_NAME}:latest"

        TF_IN_AUTOMATION = 'true'
        TF_VAR_FILE = "terraform/environments/${params.ENVIRONMENT}.tfvars"
        GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-service-account-key')
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
                                -reconfigure \
                                -no-color
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
                        sh 'terraform validate -no-color'
                    }
                }
            }
        }

        stage('Fetch Secrets from GCP Secret Manager') {
            steps {
                script {
                    def fetchSecret = { secretName, placeholder ->
                        try {
                            return sh(
                                script: """
                                    gcloud secrets versions access latest \
                                        --secret=vhealth-${params.ENVIRONMENT}-${secretName} \
                                        --project=${GCP_PROJECT_ID} 2>/dev/null \
                                    || echo '${placeholder}'
                                """,
                                returnStdout: true
                            ).trim()
                        } catch (Exception e) {
                            return placeholder
                        }
                    }

                    echo 'Fetching secrets from GCP Secret Manager...'

                    env.TF_VAR_secret_key = sh(
                        script: "python3 -c 'import secrets; print(secrets.token_urlsafe(32))'",
                        returnStdout: true
                    ).trim()

                    env.TF_VAR_google_client_id     = fetchSecret("google-client-id", "placeholder-client-id")
                    env.TF_VAR_google_client_secret = fetchSecret("google-client-secret", "placeholder-client-secret")
                    env.TF_VAR_mail_username        = fetchSecret("mail-username", "placeholder@example.com")
                    env.TF_VAR_mail_password        = fetchSecret("mail-password", "placeholder-password")

                    echo 'Secrets fetched successfully!'
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
                                -out=tfplan \
                                -no-color
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
                        sh 'terraform apply -auto-approve -no-color tfplan'

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

                    def cloudRunService = sh(
                        script: 'cd terraform && terraform output -raw cloud_run_service_name',
                        returnStdout: true
                    ).trim()

                    def serviceAccount = sh(
                        script: 'cd terraform && terraform output -raw cloud_run_service_account_email',
                        returnStdout: true
                    ).trim()

                    def vpcConnector = sh(
                        script: 'cd terraform && terraform output -raw vpc_connector_id',
                        returnStdout: true
                    ).trim()

                    sh """
                        gcloud run deploy ${cloudRunService} \
                            --image ${IMAGE_FULL} \
                            --platform managed \
                            --region ${GCP_REGION} \
                            --project ${GCP_PROJECT_ID} \
                            --service-account ${serviceAccount} \
                            --vpc-connector ${vpcConnector} \
                            --vpc-egress private-ranges-only \
                            --set-env-vars "DEBUG=${params.ENVIRONMENT == 'dev' ? 'True' : 'False'}" \
                            --set-env-vars "LOG_LEVEL=INFO" \
                            --set-env-vars "APP_NAME=VHealth Backend" \
                            --set-env-vars "ENVIRONMENT=${params.ENVIRONMENT}" \
                            --set-secrets "DATABASE_URL=vhealth-${params.ENVIRONMENT}-database-url:latest" \
                            --set-secrets "SECRET_KEY=vhealth-${params.ENVIRONMENT}-secret-key:latest" \
                            --set-secrets "GOOGLE_CLIENT_ID=vhealth-${params.ENVIRONMENT}-google-client-id:latest" \
                            --set-secrets "GOOGLE_CLIENT_SECRET=vhealth-${params.ENVIRONMENT}-google-client-secret:latest" \
                            --set-secrets "MAIL_USERNAME=vhealth-${params.ENVIRONMENT}-mail-username:latest" \
                            --set-secrets "MAIL_PASSWORD=vhealth-${params.ENVIRONMENT}-mail-password:latest" \
                            --cpu 1 \
                            --memory 512Mi \
                            --min-instances 0 \
                            --max-instances 10 \
                            --timeout 300 \
                            --concurrency 80 \
                            --allow-unauthenticated \
                            --quiet
                    """

                    def serviceUrl = sh(
                        script: "gcloud run services describe ${cloudRunService} --region=${GCP_REGION} --format='value(status.url)'",
                        returnStdout: true
                    ).trim()

                    echo "=========================================="
                    echo "Service deployed successfully!"
                    echo "Service URL: ${serviceUrl}"
                    echo "=========================================="
                }
            }
        }

        stage('Smoke Tests') {
            steps {
                script {
                    echo 'Running smoke tests...'

                    def cloudRunService = sh(
                        script: 'cd terraform && terraform output -raw cloud_run_service_name',
                        returnStdout: true
                    ).trim()

                    def serviceUrl = sh(
                        script: "gcloud run services describe ${cloudRunService} --region=${GCP_REGION} --project=${GCP_PROJECT_ID} --format='value(status.url)'",
                        returnStdout: true
                    ).trim()

                    sh """
                        echo "Testing service at: ${serviceUrl}"

                        echo "Testing health endpoint..."
                        curl -f ${serviceUrl}/health || exit 1

                        echo "Testing root endpoint..."
                        curl -f ${serviceUrl}/ || exit 1

                        echo "All smoke tests passed!"
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
            sh '''
                docker system prune -f || true
            '''
        }
    }
}
