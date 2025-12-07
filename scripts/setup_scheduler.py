#!/usr/bin/env python3
"""
Setup Cloud Scheduler job for batch notification processing.

Usage:
    python scripts/setup_scheduler.py --project=vhealth-dev --backend-url=https://api.vhealth.io.vn

Requirements:
    - gcloud CLI authenticated
    - Cloud Scheduler API enabled
    - Service account with appropriate permissions
"""

import argparse
import sys

from google.cloud import scheduler_v1
from google.api_core import exceptions


def create_scheduler_job(
    project_id: str,
    location: str,
    backend_url: str,
    service_account: str,
    schedule: str = "*/5 * * * *",
    job_name: str = "process-pending-notifications",
) -> None:
    """Create or update Cloud Scheduler job.

    Args:
        project_id: GCP project ID
        location: Scheduler location (e.g., asia-southeast1)
        backend_url: Backend URL for API calls
        service_account: Service account for OIDC authentication
        schedule: Cron schedule (default: every 5 minutes)
        job_name: Job name
    """
    client = scheduler_v1.CloudSchedulerClient()

    parent = f"projects/{project_id}/locations/{location}"
    job_path = f"{parent}/jobs/{job_name}"

    job = {
        "name": job_path,
        "description": "Process pending workout notifications every 5 minutes",
        "schedule": schedule,
        "time_zone": "UTC",
        "http_target": {
            "uri": f"{backend_url}/api/v1/notifications/process-batch",
            "http_method": scheduler_v1.HttpMethod.POST,
            "headers": {
                "Content-Type": "application/json",
            },
            "oidc_token": {
                "service_account_email": service_account,
                "audience": backend_url,
            },
        },
        "retry_config": {
            "retry_count": 3,
            "min_backoff_duration": {"seconds": 5},
            "max_backoff_duration": {"seconds": 300},
            "max_doublings": 5,
        },
    }

    try:
        # Try to create the job
        response = client.create_job(request={"parent": parent, "job": job})
        print(f"Created scheduler job: {response.name}")

    except exceptions.AlreadyExists:
        # Job exists, update it
        print(f"Job {job_name} already exists, updating...")

        response = client.update_job(request={"job": job})
        print(f"Updated scheduler job: {response.name}")

    # Print job details
    print("\nScheduler job configuration:")
    print(f"  Schedule: {schedule} (every 5 minutes)")
    print(f"  Time zone: UTC")
    print(f"  Target URL: {backend_url}/api/v1/notifications/process-batch")
    print(f"  Service account: {service_account}")
    print(f"  Retry config:")
    print(f"    retry_count: 3")
    print(f"    min_backoff: 5s")
    print(f"    max_backoff: 300s")


def delete_scheduler_job(project_id: str, location: str, job_name: str) -> None:
    """Delete Cloud Scheduler job.

    Args:
        project_id: GCP project ID
        location: Scheduler location
        job_name: Job name to delete
    """
    client = scheduler_v1.CloudSchedulerClient()
    job_path = f"projects/{project_id}/locations/{location}/jobs/{job_name}"

    try:
        client.delete_job(request={"name": job_path})
        print(f"Deleted scheduler job: {job_path}")
    except exceptions.NotFound:
        print(f"Job not found: {job_path}")


def pause_scheduler_job(project_id: str, location: str, job_name: str) -> None:
    """Pause Cloud Scheduler job.

    Args:
        project_id: GCP project ID
        location: Scheduler location
        job_name: Job name to pause
    """
    client = scheduler_v1.CloudSchedulerClient()
    job_path = f"projects/{project_id}/locations/{location}/jobs/{job_name}"

    response = client.pause_job(request={"name": job_path})
    print(f"Paused scheduler job: {response.name}")


def resume_scheduler_job(project_id: str, location: str, job_name: str) -> None:
    """Resume Cloud Scheduler job.

    Args:
        project_id: GCP project ID
        location: Scheduler location
        job_name: Job name to resume
    """
    client = scheduler_v1.CloudSchedulerClient()
    job_path = f"projects/{project_id}/locations/{location}/jobs/{job_name}"

    response = client.resume_job(request={"name": job_path})
    print(f"Resumed scheduler job: {response.name}")


def main():
    parser = argparse.ArgumentParser(
        description="Setup Cloud Scheduler job for notification processing"
    )
    parser.add_argument(
        "--project",
        required=True,
        help="GCP project ID",
    )
    parser.add_argument(
        "--location",
        default="asia-southeast1",
        help="Scheduler location (default: asia-southeast1)",
    )
    parser.add_argument(
        "--backend-url",
        required=True,
        help="Backend URL (e.g., https://api.vhealth.io.vn)",
    )
    parser.add_argument(
        "--service-account",
        help="Service account email for OIDC (default: cloud-scheduler@PROJECT.iam.gserviceaccount.com)",
    )
    parser.add_argument(
        "--schedule",
        default="*/5 * * * *",
        help="Cron schedule (default: */5 * * * * - every 5 minutes)",
    )
    parser.add_argument(
        "--job-name",
        default="process-pending-notifications",
        help="Job name (default: process-pending-notifications)",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete the scheduler job instead of creating",
    )
    parser.add_argument(
        "--pause",
        action="store_true",
        help="Pause the scheduler job",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume the scheduler job",
    )

    args = parser.parse_args()

    # Default service account
    service_account = args.service_account or f"cloud-scheduler@{args.project}.iam.gserviceaccount.com"

    try:
        if args.delete:
            delete_scheduler_job(args.project, args.location, args.job_name)
        elif args.pause:
            pause_scheduler_job(args.project, args.location, args.job_name)
        elif args.resume:
            resume_scheduler_job(args.project, args.location, args.job_name)
        else:
            create_scheduler_job(
                project_id=args.project,
                location=args.location,
                backend_url=args.backend_url,
                service_account=service_account,
                schedule=args.schedule,
                job_name=args.job_name,
            )

            print("\n" + "=" * 60)
            print("Service Account Setup")
            print("=" * 60)
            print(f"""
If you haven't created the service account yet, run:

# Create service account
gcloud iam service-accounts create cloud-scheduler \\
    --display-name="Cloud Scheduler" \\
    --project={args.project}

# Grant Cloud Run invoker role
gcloud projects add-iam-policy-binding {args.project} \\
    --member="serviceAccount:cloud-scheduler@{args.project}.iam.gserviceaccount.com" \\
    --role="roles/run.invoker"
""")

        print("\nSetup complete!")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
