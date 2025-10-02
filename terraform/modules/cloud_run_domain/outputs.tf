output "load_balancer_ip" {
  description = "Static IP address of the load balancer - add this to your DNS A record"
  value       = google_compute_global_address.default.address
}

output "domain_name" {
  description = "Domain name configured for this service"
  value       = var.domain_name
}

output "ssl_certificate_status" {
  description = "Status of the SSL certificate (check if ACTIVE)"
  value       = google_compute_managed_ssl_certificate.default.managed[0].status
}

output "ssl_certificate_name" {
  description = "Name of the managed SSL certificate"
  value       = google_compute_managed_ssl_certificate.default.name
}

output "backend_service_name" {
  description = "Name of the backend service"
  value       = google_compute_backend_service.default.name
}

output "dns_configuration" {
  description = "DNS configuration instructions"
  value = <<-EOT
    Add the following A record to your DNS provider (matbao.net):
    
    Type: A
    Name: ${split(".", var.domain_name)[0]}
    Value: ${google_compute_global_address.default.address}
    TTL: 3600
    
    Then wait 5-15 minutes for DNS propagation and SSL certificate provisioning.
    
    Check certificate status with:
    gcloud compute ssl-certificates describe ${google_compute_managed_ssl_certificate.default.name} --global --project=${var.project_id}
  EOT
}
