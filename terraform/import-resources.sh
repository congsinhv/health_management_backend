#!/bin/bash
# Import existing GCP resources into Terraform state
set -e

cd "$(dirname "$0")"
export GOOGLE_APPLICATION_CREDENTIALS=/Users/synh/vhealth-prod-sa-key.json

echo "=== Importing GCP Resources ==="
echo""

# Import service accounts
echo "Importing Cloud Run service account..."
terraform import \
  -var-file="environments/prod.tfvars" \
  -var-file="environments/prod.auto.tfvars" \
  google_service_account.cloud_run_sa \
  "projects/vhealth-prod/serviceAccounts/vhealth-backend-prod@vhealth-prod.iam.gserviceaccount.com" || true

echo "Importing Cloud Scheduler service account..."
terraform import \
  -var-file="environments/prod.tfvars" \
  -var-file="environments/prod.auto.tfvars" \
  google_service_account.cloud_scheduler_sa \
  "projects/vhealth-prod/serviceAccounts/vhealth-scheduler-prod@vhealth-prod.iam.gserviceaccount.com" || true

# Import Cloud SQL
echo "Importing Cloud SQL instance..."
terraform import \
  -var-file="environments/prod.tfvars" \
  -var-file="environments/prod.auto.tfvars" \
  module.cloud_sql.google_sql_database_instance.instance \
  "vhealth-prod/vhealth-backend-db-prod" || true

# Import VPC Connector
echo "Importing VPC Connector..."
terraform import \
  -var-file="environments/prod.tfvars" \
  -var-file="environments/prod.auto.tfvars" \
  module.vpc_connector.google_vpc_access_connector.connector \
  "projects/vhealth-prod/locations/asia-southeast1/connectors/vhealth-vpc-conn-prod" || true

# Import Redis
echo "Importing Redis instance..."
terraform import \
  -var-file="environments/prod.tfvars" \
  -var-file="environments/prod.auto.tfvars" \
  module.memorystore.google_redis_instance.cache \
  "projects/vhealth-prod/locations/asia-southeast1/instances/vhealth-cache-prod" || true

# Import Redis auth secret
echo "Importing Redis auth secret..."
terraform import \
  -var-file="environments/prod.tfvars" \
  -var-file="environments/prod.auto.tfvars" \
  module.memorystore.google_secret_manager_secret.redis_auth \
  "projects/878309847532/secrets/vhealth-cache-prod-auth-string" || true

echo ""
echo "=== Import Complete! ==="
echo ""
echo "Verifying imported resources..."
terraform state list | grep -E "(service_account|sql|redis|vpc)"
