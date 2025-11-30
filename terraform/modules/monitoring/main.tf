# Monitoring Dashboard for VHealth Microservices

# Create comprehensive monitoring dashboard
resource "google_monitoring_dashboard" "microservices_dashboard" {
  project = var.project_id

  dashboard_json = jsonencode({
    displayName = "${var.environment} VHealth Microservices Dashboard"
    gridLayout = {
      columns = "2"
      widgets = flatten([
        # Main API Widgets
        [
          {
            title = "Main API - Request Rate"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.services.main_api.service_name}\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/container/instance_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.services.main_api.service_name}\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_MEAN"
                    }
                  }
                }]
                timeshiftDuration = "0s"
                chartOptions = {
                  mode = "COLOR"
                  scale = 1
                }
                yAxis = {
                  scale = "LINEAR"
                  label = "Requests/sec"
                }
              }
            }
          },
          {
            title = "Main API - P95 Latency"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_latencies\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.services.main_api.service_name}\" metric.labels.response_time_bucket = "95"
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_PERCENTILE_95"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              chartOptions = {
                mode = "COLOR"
                scale = 1
              }
              yAxis = {
                scale = "LINEAR"
                label = "Latency (ms)"
              }
            }
          },
          {
            title = "Main API - Error Rate"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.services.main_api.service_name}\" metric.labels.response_code_class!=\"2xx\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              chartOptions = {
                mode = "COLOR"
                scale = 1
              }
              yAxis = {
                scale = "LINEAR"
                label = "Error Rate"
              }
            }
          },
          {
            title = "Main API - Instance Count"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/container/instance_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.services.main_api.service_name}\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_MEAN"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              chartOptions = {
                mode = "COLOR"
                scale = 1
              }
              yAxis = {
                scale = "LINEAR"
                label = "Instances"
              }
            }
          }
        ],
        # Chat AI Widgets
        [
          {
            title = "Chat AI - Request Rate"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.services.chat_ai.service_name}\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              chartOptions = {
                mode = "COLOR"
                scale = 1
              }
              yAxis = {
                scale = "LINEAR"
                label = "Requests/sec"
              }
            }
          },
          {
            title = "Chat AI - P95 Latency"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_latencies\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.services.chat_ai.service_name}\" metric.labels.response_time_bucket = "95"
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_PERCENTILE_95"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              chartOptions = {
                mode = "COLOR"
                scale = 1
              }
              yAxis = {
                scale = "LINEAR"
                label = "Latency (ms)"
              }
            }
          },
          {
            title = "Chat AI - Error Rate"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.services.chat_ai.service_name}\" metric.labels.response_code_class!=\"2xx\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              chartOptions = {
                mode = "COLOR"
                scale = 1
              }
              yAxis = {
                scale = "LINEAR"
                label = "Error Rate"
              }
            }
          },
          {
            title = "Chat AI - Instance Count"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/container/instance_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.services.chat_ai.service_name}\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_MEAN"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              chartOptions = {
                mode = "COLOR"
                scale = 1
              }
              yAxis = {
                scale = "LINEAR"
                label = "Instances"
              }
            }
          }
        ],
        # Prediction Service Widgets
        [
          {
            title = "Prediction - Request Rate"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.services.prediction.service_name}\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              chartOptions = {
                mode = "COLOR"
                scale = 1
              }
              yAxis = {
                scale = "LINEAR"
                label = "Requests/sec"
              }
            }
          },
          {
            title = "Prediction - P95 Latency"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_latencies\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.services.prediction.service_name}\" metric.labels.response_time_bucket = "95"
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_PERCENTILE_95"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              chartOptions = {
                mode = "COLOR"
                scale = 1
              }
              yAxis = {
                scale = "LINEAR"
                label = "Latency (ms)"
              }
            }
          },
          {
            title = "Prediction - Error Rate"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/request_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.services.prediction.service_name}\" metric.labels.response_code_class!=\"2xx\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              chartOptions = {
                mode = "COLOR"
                scale = 1
              }
              yAxis = {
                scale = "LINEAR"
                label = "Error Rate"
              }
            }
          },
          {
            title = "Prediction - Cold Starts"
            xyChart = {
              dataSets = [{
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "metric.type=\"run.googleapis.com/container/startup_count\" resource.type=\"cloud_run_revision\" resource.labels.service_name=\"${var.services.prediction.service_name}\""
                    aggregation = {
                      alignmentPeriod = "60s"
                      perSeriesAligner = "ALIGN_SUM"
                    }
                  }
                }
              }]
              timeshiftDuration = "0s"
              chartOptions = {
                mode = "COLOR"
                scale = 1
              }
              yAxis = {
                scale = "LINEAR"
                label = "Cold Starts/min"
              }
            }
          }
        ]
      ])
    }
  })
}