output "job_name" {
  description = "Cloud Scheduler job name"
  value       = google_cloud_scheduler_job.job.name
}

output "job_id" {
  description = "Cloud Scheduler job ID"
  value       = google_cloud_scheduler_job.job.id
}

output "schedule" {
  description = "Cron schedule expression"
  value       = google_cloud_scheduler_job.job.schedule
}

output "http_target_uri" {
  description = "HTTP target URI"
  value       = google_cloud_scheduler_job.job.http_target[0].uri
}

output "state" {
  description = "The state of the scheduler job (ENABLED or PAUSED)"
  value       = var.paused ? "PAUSED" : "ENABLED"
}

