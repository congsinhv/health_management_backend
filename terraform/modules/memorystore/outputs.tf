output "redis_host" {
  description = "Redis instance host"
  value       = google_redis_instance.cache.host
}

output "redis_port" {
  description = "Redis instance port"
  value       = google_redis_instance.cache.port
}

output "redis_url" {
  description = "Redis connection URL (without auth)"
  value       = "redis://${google_redis_instance.cache.host}:${google_redis_instance.cache.port}"
}

output "redis_auth_secret" {
  description = "Secret Manager secret ID for auth string"
  value       = google_secret_manager_secret.redis_auth.secret_id
}

output "redis_instance_id" {
  description = "Full Redis instance ID"
  value       = google_redis_instance.cache.id
}

output "redis_memory_size_gb" {
  description = "Provisioned memory size"
  value       = google_redis_instance.cache.memory_size_gb
}

output "redis_tier" {
  description = "Redis tier"
  value       = google_redis_instance.cache.tier
}