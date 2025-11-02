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
        booleanParam(
            name: 'REBUILD_BASE_IMAGE',
            defaultValue: false,
            description: 'Rebuild base image with dependencies (set to true when requirements-prod.txt changes)'
        )
    }

    environment {
        GCP_REGION = 'asia-southeast1'
        ENV = "${params.ENVIRONMENT}"
        GCP_PROJECT_ID = "${params.ENVIRONMENT == 'prod' ? 'vhealth-prod' : 'vhealth-dev'}"
        TF_BACKEND_BUCKET = "${GCP_PROJECT_ID}-backend-tfstate"

        ARTIFACT_REGISTRY_REPO = "vhealth-backend-${params.ENVIRONMENT}"
        IMAGE_NAME = "vhealth-backend"
        BASE_IMAGE_NAME = "vhealth-backend-base"
        IMAGE_TAG = "${env.BUILD_NUMBER}-${env.GIT_COMMIT.take(7)}"
        IMAGE_FULL = "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/${IMAGE_NAME}:${IMAGE_TAG}"
        IMAGE_LATEST = "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/${IMAGE_NAME}:latest"
        BASE_IMAGE_LATEST = "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${ARTIFACT_REGISTRY_REPO}/${BASE_IMAGE_NAME}:latest"

        TF_IN_AUTOMATION = 'true'
        TF_VAR_FILE = "terraform/environments/${params.ENVIRONMENT}.tfvars"
        GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-service-account-key')
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timeout(time: 60, unit: 'MINUTES')
        timestamps()
        disableConcurrentBuilds()
        skipDefaultCheckout(false)
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

        stage('Terraform Init & Validate') {
            steps {
                dir('terraform') {
                    script {
                        echo 'Initializing Terraform...'
                        sh """
                            terraform init \
                                -backend-config="bucket=${TF_BACKEND_BUCKET}" \
                                -backend-config="prefix=terraform/state/${params.ENVIRONMENT}" \
                                -reconfigure \
                                -no-color \
                                -upgrade
                        """
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

        stage('Setup Q&A Models & Terraform Plan') {
            parallel {
                stage('Setup Q&A Models') {
                    steps {
                        script {
                            echo 'Setting up Q&A model storage...'

                            env.GCS_MODEL_BUCKET = "vhealth-${params.ENVIRONMENT}-models"

                            def bucketExists = sh(
                                script: "gsutil ls -b gs://${GCS_MODEL_BUCKET} 2>/dev/null || echo 'not_found'",
                                returnStdout: true
                            ).trim()
                            if (bucketExists.contains('not_found')) {
                                echo "Creating GCS bucket: ${GCS_MODEL_BUCKET}"
                                sh """
                                    gsutil mb -p ${GCP_PROJECT_ID} -l ${GCP_REGION} gs://${GCS_MODEL_BUCKET}
                                    gsutil lifecycle set - gs://${GCS_MODEL_BUCKET} <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": 90, "matchesPrefix": ["tmp/"]}
      }
    ]
  }
}
EOF
                                """
                            } else {
                                echo "GCS bucket already exists: ${GCS_MODEL_BUCKET}"
                            }
                            def modelExists = sh(
                                script: "gsutil -q stat gs://${GCS_MODEL_BUCKET}/models/vietnamese-sbert/config.json || echo 'not_found'",
                                returnStdout: true
                            ).trim()
                            if (modelExists.contains('not_found')) {
                                echo """
========================================
WARNING: Q&A model files not found in GCS!
========================================
To upload model files, run:
  gsutil -m cp -r models/vietnamese-sbert gs://${GCS_MODEL_BUCKET}/models/
  gsutil -m cp data.xlsx gs://${GCS_MODEL_BUCKET}/data/
  gsutil -m cp tuvung.txt gs://${GCS_MODEL_BUCKET}/data/

The service will attempt to download from Hugging Face as fallback.
========================================
                                """
                            } else {
                                echo "Model files found in GCS bucket"
                            }
                            // Ensure OpenRouter API key secret exists
                            def secretExists = sh(
                                script: "gcloud secrets describe vhealth-${params.ENVIRONMENT}-openrouter-api-key --project=${GCP_PROJECT_ID} 2>/dev/null || echo 'not_found'",
                                returnStdout: true
                            ).trim()
                            if (secretExists.contains('not_found')) {
                                echo """
========================================
WARNING: OpenRouter API key secret not found!
========================================
To create the secret, run:
  echo -n 'your-api-key-here' | gcloud secrets create vhealth-${params.ENVIRONMENT}-openrouter-api-key \\
    --project=${GCP_PROJECT_ID} \\
    --data-file=- \\
    --replication-policy=automatic

AI summarization will not be available without this secret.
========================================
                                """
                            } else {
                                echo "OpenRouter API key secret exists"
                            }
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
                                        -no-color \
                                        -compact-warnings
                                """
                            }
                        }
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

        stage('Build/Pull Base Image') {
            steps {
                script {
                    echo "Base Image Strategy: ${params.REBUILD_BASE_IMAGE ? 'REBUILD' : 'USE EXISTING'}"

                    def baseImageCheck = sh(
                        script: "docker pull ${BASE_IMAGE_LATEST} 2>&1",
                        returnStatus: true
                    )

                    def imageNotFound = (baseImageCheck != 0)

                    if (params.REBUILD_BASE_IMAGE || imageNotFound) {
                        if (imageNotFound && !params.REBUILD_BASE_IMAGE) {
                            echo "Base image not found, auto-rebuilding (first build or missing image)..."
                        } else {
                            echo "Rebuilding base image with dependencies..."
                        }

                        def previousBaseImage = "${BASE_IMAGE_LATEST}"
                        sh """
                            docker pull ${previousBaseImage} || echo "No previous base image found"
                        """
                        sh """
                            DOCKER_BUILDKIT=1 docker build \
                                -f Dockerfile.base \
                                --cache-from ${previousBaseImage} \
                                --tag ${BASE_IMAGE_LATEST} \
                                --progress=plain \
                                .
                        """
                        sh """
                            docker push ${BASE_IMAGE_LATEST}
                        """
                        echo "Base image rebuilt and pushed: ${BASE_IMAGE_LATEST}"
                    } else {
                        echo "Using existing base image: ${BASE_IMAGE_LATEST}"
                    }
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                script {
                    echo "Building application image: ${IMAGE_FULL}"
                    echo "Using base image: ${BASE_IMAGE_LATEST}"

                    def previousImage = "${IMAGE_LATEST}"
                    sh """
                        docker pull ${previousImage} || echo "No previous image found, building from scratch"
                    """
                    sh """
                        DOCKER_BUILDKIT=1 docker build \
                            --build-arg BASE_IMAGE=${BASE_IMAGE_LATEST} \
                            --build-arg BUILD_DATE=\$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
                            --build-arg VERSION=${IMAGE_TAG} \
                            --build-arg GIT_COMMIT=${GIT_COMMIT} \
                            --cache-from ${previousImage} \
                            --tag ${IMAGE_FULL} \
                            --tag ${IMAGE_LATEST} \
                            --progress=plain \
                            .
                    """
                }
            }
        }

        stage('Push to Artifact Registry') {
            steps {
                script {
                    echo 'Pushing image to Artifact Registry...'
                    // Push latest first to update cache for next build
                    sh """
                        docker push ${IMAGE_LATEST}
                        docker push ${IMAGE_FULL}
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

                    def revisionSuffix = "${env.BUILD_NUMBER}-${env.GIT_COMMIT.take(7)}"
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
                            --set-env-vars "QA_ENABLED=true" \
                            --set-env-vars "GCP_PROJECT_ID=${GCP_PROJECT_ID}" \
                            --set-env-vars "GCP_MODEL_BUCKET=vhealth-${params.ENVIRONMENT}-models" \
                            --set-env-vars "MODEL_AUTO_DOWNLOAD=true" \
                            --set-env-vars "GCP_MODEL_BLOB_PATH=models/vietnamese-sbert/" \
                            --set-env-vars "GCP_DATA_BLOB_PATH=data/" \
                            --set-secrets "DATABASE_URL=vhealth-${params.ENVIRONMENT}-database-url:latest" \
                            --set-secrets "SECRET_KEY=vhealth-${params.ENVIRONMENT}-secret-key:latest" \
                            --set-secrets "GOOGLE_CLIENT_ID=vhealth-${params.ENVIRONMENT}-google-client-id:latest" \
                            --set-secrets "GOOGLE_CLIENT_SECRET=vhealth-${params.ENVIRONMENT}-google-client-secret:latest" \
                            --set-secrets "MAIL_USERNAME=vhealth-${params.ENVIRONMENT}-mail-username:latest" \
                            --set-secrets "MAIL_PASSWORD=vhealth-${params.ENVIRONMENT}-mail-password:latest" \
                            --set-secrets "OPENROUTER_API_KEY=vhealth-${params.ENVIRONMENT}-openrouter-api-key:latest" \
                            --cpu 2 \
                            --memory 2Gi \
                            --min-instances 0 \
                            --max-instances 10 \
                            --timeout 300 \
                            --concurrency 15 \
                            --allow-unauthenticated \
                            --revision-suffix ${revisionSuffix} \
                            --no-traffic \
                            --quiet
                    """
                    sh """
                        gcloud run services update-traffic ${cloudRunService} \
                            --to-revisions ${cloudRunService}-${revisionSuffix}=100 \
                            --region ${GCP_REGION} \
                            --project ${GCP_PROJECT_ID} \
                            --quiet
                    """

                    def serviceUrl = sh(
                        script: "gcloud run services describe ${cloudRunService} --region=${GCP_REGION} --project=${GCP_PROJECT_ID} --format='value(status.url)'",
                        returnStdout: true
                    ).trim()

                    echo "=========================================="
                    echo "Service deployed successfully!"
                    echo "Revision: ${revisionSuffix}"
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

                        echo "Testing Q&A health endpoint..."
                        curl -f ${serviceUrl}/api/v1/qa/health || exit 1

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
