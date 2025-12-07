output "queue_name" {
  description = "The name of the Cloud Tasks queue"
  value       = google_cloud_tasks_queue.queue.name
}

output "queue_id" {
  description = "The fully-qualified resource ID of the queue"
  value       = google_cloud_tasks_queue.queue.id
}

output "queue_path" {
  description = "The full path of the queue (projects/PROJECT/locations/LOCATION/queues/QUEUE)"
  value       = "projects/${var.project_id}/locations/${var.location}/queues/${google_cloud_tasks_queue.queue.name}"
}

output "service_account_email" {
  description = "The email of the Cloud Tasks invoker service account"
  value       = var.create_service_account ? google_service_account.cloudtasks_invoker[0].email : null
}

output "service_account_id" {
  description = "The unique ID of the Cloud Tasks invoker service account"
  value       = var.create_service_account ? google_service_account.cloudtasks_invoker[0].unique_id : null
}

