# Alert Policies for VHealth Microservices

# Create notification channel reference (managed separately)
data "google_monitoring_notification_channel" "default" {
  display_name = "VHealth ${var.environment} Alerts"
}

# High Error Rate Alert for Main API
resource "google_monitoring_alert_policy" "main_api_error_rate" {
  display_name = "${var.environment} Main API High Error Rate"
  combiner     = "OR"
  enabled       = var.alert_enabled
  notification_channels = [data.google_monitoring_notification_channel.default.name]

  conditions {
    display_name = "Main API error rate > ${lookup(var.services, "main_api", {}).error_rate_threshold * 100}%"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${lookup(var.services, "main_api", {}).service_name}\" metric.labels.response_code_class=\"4xx\" OR metric.labels.response_code_class=\"5xx\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = lookup(var.services, "main_api", {}).error_rate_threshold

      aggregations {
        alignment_period     = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }
}

# High Latency Alert for Main API
resource "google_monitoring_alert_policy" "main_api_latency" {
  display_name = "${var.environment} Main API High Latency"
  combiner     = "OR"
  enabled       = var.alert_enabled
  notification_channels = [data.google_monitoring_notification_channel.default.name]

  conditions {
    display_name = "Main API P95 latency > ${lookup(var.services, "main_api", {}).latency_threshold_ms}ms"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_latencies\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${lookup(var.services, "main_api", {}).service_name}\" metric.labels.response_time_bucket=\"95\""
      duration        = "120s"
      comparison      = "COMPARISON_GT"
      threshold_value = lookup(var.services, "main_api", {}).latency_threshold_ms

      aggregations {
        alignment_period     = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_95"
      }
    }
  }
}

# High Error Rate Alert for Chat AI
resource "google_monitoring_alert_policy" "chat_ai_error_rate" {
  display_name = "${var.environment} Chat AI High Error Rate"
  combiner     = "OR"
  enabled       = var.alert_enabled
  notification_channels = [data.google_monitoring_notification_channel.default.name]

  conditions {
    display_name = "Chat AI error rate > ${lookup(var.services, "chat_ai", {}).error_rate_threshold * 100}%"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${lookup(var.services, "chat_ai", {}).service_name}\" metric.labels.response_code_class=\"4xx\" OR metric.labels.response_code_class=\"5xx\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = lookup(var.services, "chat_ai", {}).error_rate_threshold

      aggregations {
        alignment_period     = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }
}

# High Latency Alert for Chat AI
resource "google_monitoring_alert_policy" "chat_ai_latency" {
  display_name = "${var.environment} Chat AI High Latency"
  combiner     = "OR"
  enabled       = var.alert_enabled
  notification_channels = [data.google_monitoring_notification_channel.default.name]

  conditions {
    display_name = "Chat AI P95 latency > ${lookup(var.services, "chat_ai", {}).latency_threshold_ms}ms"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_latencies\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${lookup(var.services, "chat_ai", {}).service_name}\" metric.labels.response_time_bucket=\"95\""
      duration        = "120s"
      comparison      = "COMPARISON_GT"
      threshold_value = lookup(var.services, "chat_ai", {}).latency_threshold_ms

      aggregations {
        alignment_period     = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_95"
      }
    }
  }
}

# High Error Rate Alert for Prediction Service
resource "google_monitoring_alert_policy" "prediction_error_rate" {
  display_name = "${var.environment} Prediction Service High Error Rate"
  combiner     = "OR"
  enabled       = var.alert_enabled
  notification_channels = [data.google_monitoring_notification_channel.default.name]

  conditions {
    display_name = "Prediction error rate > ${lookup(var.services, "prediction", {}).error_rate_threshold * 100}%"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${lookup(var.services, "prediction", {}).service_name}\" metric.labels.response_code_class=\"4xx\" OR metric.labels.response_code_class=\"5xx\""
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = lookup(var.services, "prediction", {}).error_rate_threshold

      aggregations {
        alignment_period     = "60s"
        per_series_aligner = "ALIGN_RATE"
      }
    }
  }
}

# High Latency Alert for Prediction Service
resource "google_monitoring_alert_policy" "prediction_latency" {
  display_name = "${var.environment} Prediction Service High Latency"
  combiner     = "OR"
  enabled       = var.alert_enabled
  notification_channels = [data.google_monitoring_notification_channel.default.name]

  conditions {
    display_name = "Prediction P95 latency > ${lookup(var.services, "prediction", {}).latency_threshold_ms}ms"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_latencies\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${lookup(var.services, "prediction", {}).service_name}\" metric.labels.response_time_bucket=\"95\""
      duration        = "120s"
      comparison      = "COMPARISON_GT"
      threshold_value = lookup(var.services, "prediction", {}).latency_threshold_ms

      aggregations {
        alignment_period     = "60s"
        per_series_aligner = "ALIGN_PERCENTILE_95"
      }
    }
  }
}

# Cold Start Alert for Prediction Service (on-demand service)
resource "google_monitoring_alert_policy" "prediction_cold_starts" {
  display_name = "${var.environment} Prediction Service High Cold Starts"
  combiner     = "OR"
  enabled       = var.alert_enabled
  notification_channels = [data.google_monitoring_notification_channel.default.name]

  conditions {
    display_name = "Prediction cold starts > 5/min"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/container/startup_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${lookup(var.services, "prediction", {}).service_name}\""
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5

      aggregations {
        alignment_period     = "60s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
}

# Service Unavailable Alert (Main API)
resource "google_monitoring_alert_policy" "main_api_unavailable" {
  display_name = "${var.environment} Main API Service Unavailable"
  combiner     = "OR"
  enabled       = var.alert_enabled
  notification_channels = [data.google_monitoring_notification_channel.default.name]

  conditions {
    display_name = "Main API no requests for 5 minutes"

    condition_threshold {
      filter          = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${lookup(var.services, "main_api", {}).service_name}\""
      duration        = "300s"
      comparison      = "COMPARISON_LT"
      threshold_value = 1

      aggregations {
        alignment_period     = "60s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
}

# Cost Alert (Optional - for budget monitoring)
resource "google_monitoring_alert_policy" "budget_alert" {
  count    = var.enable_cost_alerting ? 1 : 0
  display_name = "${var.environment} Budget Alert"
  combiner     = "OR"
  enabled       = var.alert_enabled
  notification_channels = [data.google_monitoring_notification_channel.default.name]

  conditions {
    display_name = "Budget exceeded 80%"

    condition_threshold {
      filter          = "metric.type=\"billing.googleapis.com/billing_amount\" resource.labels.billing_account_id=\"${var.billing_account_id}\""
      duration        = "86400s"  # 24 hours
      comparison      = "COMPARISON_GT"
      threshold_value = var.budget_threshold

      aggregations {
        alignment_period     = "86400s"
        per_series_aligner = "ALIGN_SUM"
      }
    }
  }
}