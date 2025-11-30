# VPC network for Direct VPC Egress
resource "google_compute_network" "vpc_network" {
  name                    = "${var.environment}-vpc"
  auto_create_subnetworks = false
  project                 = var.project_id

  # Enable Private Google Access for Cloud SQL/Redis
  description = "VPC network for VHealth microservices with Direct VPC Egress"
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${var.environment}-subnet"
  ip_cidr_range = var.subnet_cidr
  region        = var.region
  network       = google_compute_network.vpc_network.id

  # Private Google Access for Cloud SQL/Redis/Memorystore
  private_ip_google_access = true

  description = "Subnet for VHealth microservices with Private Google Access"
}

# VPC Connector for backward compatibility during migration
resource "google_vpc_access_connector" "connector" {
  count = var.use_vpc_connector ? 1 : 0

  name          = "${var.environment}-vpc-connector"
  region        = var.region
  network       = google_compute_network.vpc_network.id
  ip_cidr_range = var.connector_cidr

  # Use smallest machine type for cost optimization
  machine_type = "e2-micro"
  min_instances = var.connector_min_instances
  max_instances = var.connector_max_instances

  # Cloud NAT is not needed with Direct VPC Egress
  # All traffic stays within Google's network

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [google_compute_subnetwork.subnet]
}

# Firewall rule to allow internal traffic between services
resource "google_compute_firewall" "allow_internal" {
  name    = "${var.environment}-allow-internal"
  network = google_compute_network.vpc_network.id
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["80", "443", "8080"]
  }

  allow {
    protocol = "udp"
  }

  # Allow all traffic within the same subnet (microservices)
  source_tags   = ["microservice"]
  source_ranges = [var.subnet_cidr]
  target_tags   = ["microservice"]

  description = "Allow internal traffic between microservices"
}

# Firewall rule for health checks
resource "google_compute_firewall" "allow_health_checks" {
  name    = "${var.environment}-allow-health-checks"
  network = google_compute_network.vpc_network.id
  project = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["80", "443", "8080"]
  }

  # Google Cloud health check ranges
  source_ranges = [
    "130.211.0.0/22",
    "35.191.0.0/16"
  ]

  target_tags = ["microservice"]

  description = "Allow health check traffic from Google Cloud"
}

# Private Service Connect for Cloud SQL (optional, for enhanced security)
resource "google_compute_global_address" "psc_endpoint" {
  count         = var.enable_private_service_connect ? 1 : 0
  name          = "${var.environment}-cloudsql-psc"
  project       = var.project_id
  purpose       = "PRIVATE_SERVICE_CONNECT"
  address_type  = "INTERNAL"
  network       = google_compute_network.vpc_network.id
  address       = var.private_service_connect_ip
}

# Forwarding rule for Cloud SQL Private Service Connect
resource "google_compute_forwarding_rule" "psc_forwarding_rule" {
  count               = var.enable_private_service_connect ? 1 : 0
  name                = "${var.environment}-cloudsql-psc-forwarding"
  project             = var.project_id
  region              = var.region
  ip_protocol         = "TCP"
  load_balancing_type = "INTERNAL_MANAGED"
  ports               = ["5432"]
  target              = google_compute_forwarding_rule.psc_forwarding_rule[0].target
  network             = google_compute_network.vpc_network.id
  subnetwork          = google_compute_subnetwork.subnet.id
  ip_address          = google_compute_global_address.psc_endpoint[0].address
}

# Outputs
output "network_id" {
  value = google_compute_network.vpc_network.id
  description = "VPC network ID for Direct VPC Egress"
}

output "subnet_id" {
  value = google_compute_subnetwork.subnet.id
  description = "Subnet ID for Cloud Run services"
}

output "subnet_self_link" {
  value = google_compute_subnetwork.subnet.self_link
  description = "Subnet self-link for Direct VPC Egress configuration"
}

output "connector_id" {
  value = var.use_vpc_connector ? google_vpc_access_connector.connector[0].id : null
  description = "VPC Connector ID (backward compatibility)"
}

output "psc_endpoint_ip" {
  value = var.enable_private_service_connect ? google_compute_global_address.psc_endpoint[0].address : null
  description = "Private Service Connect endpoint IP for Cloud SQL"
}