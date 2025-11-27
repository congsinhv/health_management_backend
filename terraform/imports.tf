# Import configuration for existing GCP resources

import {
  id = "projects/vhealth-prod/serviceAccounts/vhealth-backend-prod@vhealth-prod.iam.gserviceaccount.com"
  to = google_service_account.cloud_run_sa
}

import {
  id = "projects/vhealth-prod/serviceAccounts/vhealth-scheduler-prod@vhealth-prod.iam.gserviceaccount.com"
  to = google_service_account.cloud_scheduler_sa
}

import {
  id = "vhealth-prod/vhealth-backend-db-prod"
  to = module.cloud_sql.google_sql_database_instance.instance
}

import {
  id = "projects/vhealth-prod/locations/asia-southeast1/connectors/vhealth-vpc-conn-prod"
  to = module.vpc_connector.google_vpc_access_connector.connector
}

import {
  id = "projects/vhealth-prod/locations/asia-southeast1/instances/vhealth-cache-prod"
  to = module.memorystore.google_redis_instance.cache
}

import {
  id = "projects/878309847532/secrets/vhealth-cache-prod-auth-string"
  to = module.memorystore.google_secret_manager_secret.redis_auth
}
