output "bucket_name" {
  description = "The name of the storage bucket"
  value       = google_storage_bucket.bucket.name
}

output "bucket_url" {
  description = "The base URL of the bucket"
  value       = google_storage_bucket.bucket.url
}

output "bucket_self_link" {
  description = "The URI of the bucket"
  value       = google_storage_bucket.bucket.self_link
}

output "bucket_location" {
  description = "The location of the bucket"
  value       = google_storage_bucket.bucket.location
}

