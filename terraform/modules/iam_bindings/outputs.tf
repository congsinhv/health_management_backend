output "bindings_created" {
  description = "Summary of created IAM bindings"
  value = {
    main_to_chat_ai    = google_cloud_run_service_iam_member.main_api_to_chat_ai.id
    main_to_prediction = google_cloud_run_service_iam_member.main_api_to_prediction.id
    main_api_public    = google_cloud_run_service_iam_member.main_api_public.id
  }
}

output "reverse_communication_bindings" {
  description = "Reverse communication bindings (if enabled)"
  value = var.enable_reverse_communication ? {
    chat_ai_to_main_api    = google_cloud_run_service_iam_member.chat_ai_to_main_api[0].id
    prediction_to_main_api = google_cloud_run_service_iam_member.prediction_to_main_api[0].id
  } : null
}

output "debug_access_bindings" {
  description = "Debug access bindings (if enabled)"
  value = var.enable_debug_access ? {
    main_api_debugger = google_cloud_run_service_iam_member.main_api_debugger[0].id
  } : null
}

output "time_restricted_access" {
  description = "Time-restricted access binding (if enabled)"
  value = var.enable_time_restrictions ? {
    main_api_time_restricted = google_cloud_run_service_iam_member.main_api_time_restricted[0].id
  } : null
}

output "service_permissions_summary" {
  description = "Summary of service-to-service permissions"
  value = {
    main_api = {
      can_invoke_chat_ai    = true
      can_invoke_prediction = true
      public_access         = true
      developer_access      = true
      viewer_access         = true
      debug_access          = var.enable_debug_access
    }
    chat_ai = {
      can_invoke_main_api = var.enable_reverse_communication
      developer_access    = true
    }
    prediction = {
      can_invoke_main_api = var.enable_reverse_communication
      developer_access    = true
    }
  }
}