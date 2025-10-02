output "secret_names" {
  description = "Map of secret keys to secret resource names"
  value = {
    for key, secret in google_secret_manager_secret.secrets :
    key => secret.name
  }
}

output "secret_ids" {
  description = "Map of secret keys to secret IDs"
  value = {
    for key, secret in google_secret_manager_secret.secrets :
    key => secret.secret_id
  }
}

output "secret_versions" {
  description = "Map of secret keys to secret version IDs"
  value = {
    for key, version in google_secret_manager_secret_version.secret_versions :
    key => version.name
  }
  sensitive = true
}
