resource "google_redis_instance" "cache" {
  name           = var.instance_name
  tier           = var.tier
  memory_size_gb = var.memory_size_gb
  region         = var.region
  redis_version  = var.redis_version
  display_name   = var.display_name

  authorized_network = var.vpc_network
  connect_mode       = "PRIVATE_SERVICE_ACCESS"

  auth_enabled            = true
  transit_encryption_mode = "SERVER_AUTHENTICATION"

  # Standard tier only
  replica_count      = var.tier == "STANDARD_HA" ? 1 : 0
  read_replicas_mode = var.tier == "STANDARD_HA" ? "READ_REPLICAS_ENABLED" : null

  # Maintenance window
  maintenance_policy {
    weekly_maintenance_window {
      day = var.maintenance_window_day
      start_time {
        hours   = var.maintenance_window_hour
        minutes = 0
        seconds = 0
        nanos   = 0
      }
    }
  }

  # Redis configuration
  redis_configs = {
    maxmemory-policy       = "allkeys-lru"
    notify-keyspace-events = "Ex"
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    service     = "health-management-api"
  }

  depends_on = [google_project_service.redis]
}

resource "google_project_service" "redis" {
  service            = "redis.googleapis.com"
  disable_on_destroy = false
}

# Store auth string in Secret Manager
resource "google_secret_manager_secret" "redis_auth" {
  secret_id = "${var.instance_name}-auth-string"

  replication {
    auto {}
  }

  labels = {
    environment = var.environment
  }
}

resource "google_secret_manager_secret_version" "redis_auth" {
  secret      = google_secret_manager_secret.redis_auth.id
  secret_data = google_redis_instance.cache.auth_string
}