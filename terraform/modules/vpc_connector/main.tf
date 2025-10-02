resource "google_vpc_access_connector" "connector" {
  name          = var.connector_name
  region        = var.region
  network       = var.vpc_network
  ip_cidr_range = var.ip_cidr_range

  min_instances = var.min_instances
  max_instances = var.max_instances
  machine_type  = var.machine_type

  depends_on = [google_project_service.vpcaccess]
}

resource "google_project_service" "vpcaccess" {
  service            = "vpcaccess.googleapis.com"
  disable_on_destroy = false
}
