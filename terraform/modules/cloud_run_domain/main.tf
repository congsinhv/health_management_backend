# Cloud Run Domain Mapping Module
# This module sets up custom domain mapping for Cloud Run services using:
# - Global External Application Load Balancer
# - Google-managed SSL certificates
# - Static IP address

# Enable required APIs
resource "google_project_service" "certificate_manager" {
  service            = "certificatemanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "compute" {
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

# Reserve a global static IP address for the load balancer
resource "google_compute_global_address" "default" {
  name         = "${var.environment}-api-lb-ip"
  address_type = "EXTERNAL"
  ip_version   = "IPV4"

  depends_on = [google_project_service.compute]
}

# Create a serverless NEG (Network Endpoint Group) for Cloud Run
resource "google_compute_region_network_endpoint_group" "cloudrun_neg" {
  name                  = "${var.environment}-api-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region

  cloud_run {
    service = var.cloud_run_service_name
  }

  depends_on = [google_project_service.compute]
}

# Create a backend service
resource "google_compute_backend_service" "default" {
  name                  = "${var.environment}-api-backend"
  protocol              = "HTTP"
  port_name             = "http"
  timeout_sec           = 30
  enable_cdn            = var.enable_cdn
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.cloudrun_neg.id
  }

  log_config {
    enable      = true
    sample_rate = 1.0
  }
}

# Create URL map
resource "google_compute_url_map" "default" {
  name            = "${var.environment}-api-url-map"
  default_service = google_compute_backend_service.default.id

  host_rule {
    hosts        = [var.domain_name]
    path_matcher = "allpaths"
  }

  path_matcher {
    name            = "allpaths"
    default_service = google_compute_backend_service.default.id
  }
}

# Create managed SSL certificate
resource "google_compute_managed_ssl_certificate" "default" {
  name = "${var.environment}-api-ssl-cert"

  managed {
    domains = [var.domain_name]
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Create HTTPS target proxy
resource "google_compute_target_https_proxy" "default" {
  name             = "${var.environment}-api-https-proxy"
  url_map          = google_compute_url_map.default.id
  ssl_certificates = [google_compute_managed_ssl_certificate.default.id]
}

# Create HTTP to HTTPS redirect
resource "google_compute_url_map" "https_redirect" {
  name = "${var.environment}-api-https-redirect"

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "https_redirect" {
  name    = "${var.environment}-api-http-proxy"
  url_map = google_compute_url_map.https_redirect.id
}

# Create forwarding rule for HTTPS
resource "google_compute_global_forwarding_rule" "https" {
  name                  = "${var.environment}-api-https-forwarding-rule"
  ip_protocol           = "TCP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  port_range            = "443"
  target                = google_compute_target_https_proxy.default.id
  ip_address            = google_compute_global_address.default.id
}

# Create forwarding rule for HTTP (redirect to HTTPS)
resource "google_compute_global_forwarding_rule" "http" {
  name                  = "${var.environment}-api-http-forwarding-rule"
  ip_protocol           = "TCP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  port_range            = "80"
  target                = google_compute_target_http_proxy.https_redirect.id
  ip_address            = google_compute_global_address.default.id
}
