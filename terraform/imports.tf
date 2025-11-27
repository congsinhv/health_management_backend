# Import configuration for existing GCP resources

import {
  id = "projects/vhealth-prod/serviceAccounts/vhealth-backend-prod@vhealth-prod.iam.gserviceaccount.com"
  to = google_service_account.cloud_run_sa
}

import {
  id = "vhealth-prod roles/cloudsql.client serviceAccount:vhealth-backend-prod@vhealth-prod.iam.gserviceaccount.com"
  to = google_project_iam_member.cloud_run_sql_client
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

# Import existing secrets from Secret Manager
import {
  id = "projects/878309847532/secrets/vhealth-prod-google-client-id"
  to = module.secret_manager.google_secret_manager_secret.secrets["google_client_id"]
}

import {
  id = "projects/878309847532/secrets/vhealth-prod-google-client-secret"
  to = module.secret_manager.google_secret_manager_secret.secrets["google_client_secret"]
}

import {
  id = "projects/878309847532/secrets/vhealth-prod-mail-server"
  to = module.secret_manager.google_secret_manager_secret.secrets["mail_server"]
}

import {
  id = "projects/878309847532/secrets/vhealth-prod-mail-from"
  to = module.secret_manager.google_secret_manager_secret.secrets["mail_from"]
}

import {
  id = "projects/878309847532/secrets/vhealth-prod-mail-username"
  to = module.secret_manager.google_secret_manager_secret.secrets["mail_username"]
}

import {
  id = "projects/878309847532/secrets/vhealth-prod-mail-password"
  to = module.secret_manager.google_secret_manager_secret.secrets["mail_password"]
}

import {
  id = "projects/878309847532/secrets/vhealth-prod-secret-key"
  to = module.secret_manager.google_secret_manager_secret.secrets["secret_key"]
}
