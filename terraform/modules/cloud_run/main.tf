resource "google_cloud_run_v2_service" "service" {
  name     = var.service_name
  location = var.region
  ingress  = var.ingress

  template {
    service_account = var.service_account_email

    # Direct VPC Egress (preferred) or VPC Connector (backward compatibility)
    dynamic "vpc_access" {
      for_each = var.use_direct_vpc_egress ? [1] : []
      content {
        egress = "ALL_TRAFFIC"  # Route all traffic through VPC
        network_interfaces {
          network    = var.vpc_network_id
          subnetwork = var.vpc_subnet_id
        }
      }
    }

    # Fallback to VPC Connector if Direct VPC Egress not enabled
    dynamic "vpc_access" {
      for_each = var.use_direct_vpc_egress ? [] : [1]
      content {
        connector = var.vpc_connector_id
        egress    = var.vpc_egress
      }
    }

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    # Session affinity for stateful applications (Chat AI)
    dynamic "template" {
      for_each = var.session_affinity ? [1] : []
      content {
        scaling {
          session_affinity = true
        }
      }
    }

    timeout = "${var.timeout_seconds}s"

    containers {
      image = var.image

      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
        # Optional: Set minimum resources for performance
        dynamic "cpu" {
          for_each = var.cpu_minimum != null ? [1] : []
          content {
            cpu = var.cpu_minimum
          }
        }
      }

      ports {
        container_port = var.container_port
      }

      # Environment variables from secrets
      dynamic "env" {
        for_each = var.secret_env_vars
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }

      # Regular environment variables
      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      # Cloud SQL connection (only if provided)
      dynamic "env" {
        for_each = var.cloud_sql_connection_name != null ? [1] : []
        content {
          name  = "CLOUD_SQL_CONNECTION_NAME"
          value = var.cloud_sql_connection_name
        }
      }

      # Database connection string (for services with direct DB access)
      dynamic "env" {
        for_each = var.database_url != null ? [1] : []
        content {
          name  = "DATABASE_URL"
          value = var.database_url
        }
      }

      # Redis connection URL
      dynamic "env" {
        for_each = var.redis_url != null ? [1] : []
        content {
          name  = "REDIS_URL"
          value = var.redis_url
        }
      }

      # Service URLs for inter-service communication
      dynamic "env" {
        for_each = var.main_api_url != null ? [1] : []
        content {
          name  = "MAIN_API_URL"
          value = var.main_api_url
        }
      }

      dynamic "env" {
        for_each = var.chat_ai_url != null ? [1] : []
        content {
          name  = "CHAT_AI_URL"
          value = var.chat_ai_url
        }
      }

      dynamic "env" {
        for_each = var.prediction_url != null ? [1] : []
        content {
          name  = "PREDICTION_URL"
          value = var.prediction_url
        }
      }

      # Startup probe
      startup_probe {
        http_get {
          path = var.health_check_path
          port = var.container_port
        }
        initial_delay_seconds = var.startup_delay_seconds
        timeout_seconds       = var.startup_timeout_seconds
        period_seconds        = var.startup_period_seconds
        failure_threshold     = var.startup_failure_threshold
        success_threshold     = var.startup_success_threshold
      }

      # Liveness probe
      liveness_probe {
        http_get {
          path = var.health_check_path
          port = var.container_port
        }
        initial_delay_seconds = var.liveness_delay_seconds
        timeout_seconds       = var.liveness_timeout_seconds
        period_seconds        = var.liveness_period_seconds
        failure_threshold     = var.liveness_failure_threshold
        success_threshold     = var.liveness_success_threshold
      }

      # Readiness probe (optional)
      dynamic "readiness_probe" {
        for_each = var.enable_readiness_probe ? [1] : []
        content {
          http_get {
            path = var.ready_check_path
            port = var.container_port
          }
          initial_delay_seconds = var.readiness_delay_seconds
          timeout_seconds       = var.readiness_timeout_seconds
          period_seconds        = var.readiness_period_seconds
          failure_threshold     = var.readiness_failure_threshold
          success_threshold     = var.readiness_success_threshold
        }
      }

      # Volume mounts for model files or other shared data
      dynamic "volume_mounts" {
        for_each = var.volume_mounts
        content {
          name       = volume_mounts.value.name
          mount_path = volume_mounts.value.mount_path
          read_only  = volume_mounts.value.read_only
        }
      }

      # Command and arguments for container
      dynamic "command" {
        for_each = var.container_command != null ? [1] : []
        content {
          command = var.container_command
        }
      }

      dynamic "args" {
        for_each = var.container_args != null ? [1] : []
        content {
          args = var.container_args
        }
      }
    }

    # Volume definitions
    dynamic "volumes" {
      for_each = var.volumes
      content {
        name = volumes.value.name
        dynamic "empty_dir" {
          for_each = volumes.value.empty_dir != null ? [1] : []
          content {
            medium = volumes.value.empty_dir.medium
          }
        }
        dynamic "secret" {
          for_each = volumes.value.secret != null ? [1] : []
          content {
            secret_name = volumes.value.secret.name
            optional    = volumes.value.secret.optional
            dynamic "items" {
              for_each = volumes.value.secret.items != null ? volumes.value.secret.items : []
              content {
                key        = items.value.key
                path       = items.value.path
                mode       = items.value.mode
                version    = items.value.version
              }
            }
          }
        }
      }
    }

    max_instance_request_concurrency = var.concurrency

    # Resource limits and requests
    dynamic "resources" {
      for_each = var.resource_requests != null ? [1] : []
      content {
        limits = var.resource_limits
        requests = var.resource_requests
      }
    }

    labels = merge(
      {
        environment = var.environment
        managed_by  = "terraform"
      },
      var.additional_labels
    )

    annotations = merge(
      {
        "autoscaling.knative.dev/maxScale" = tostring(var.max_instances)
        "autoscaling.knative.dev/minScale" = tostring(var.min_instances)
      },
      var.use_direct_vpc_egress ? {
        "run.googleapis.com/vpc-access-egress" = "all"
      } : {},
      var.additional_annotations
    )
  }

  traffic {
    type    = var.traffic_type
    percent = 100
  }

  depends_on = [
    google_project_service.run
  ]
}

# Allow public access (if enabled)
resource "google_cloud_run_v2_service_iam_member" "public_access" {
  count   = var.allow_public_access ? 1 : 0
  project = var.project_id
  location = google_cloud_run_v2_service.service.location
  name    = google_cloud_run_v2_service.service.name
  role    = "roles/run.invoker"
  member  = "allUsers"
}

# Custom domain mapping (if enabled)
resource "google_cloud_run_domain_mapping" "custom_domain" {
  count    = var.custom_domain != null ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = var.custom_domain

  metadata {
    namespace = var.project_id
    annotations = {
      "run.googleapis.com/ingress" = var.ingress
    }
  }

  spec {
    route_name = google_cloud_run_v2_service.service.name
  }
}

resource "google_project_service" "run" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "vpc_access" {
  service            = "vpcaccess.googleapis.com"
  disable_on_destroy = false
}