#!/usr/bin/env python3
"""
Setup Cloud Tasks queue for workout notifications.

Usage:
    python scripts/setup_cloud_tasks.py --project=vhealth-dev --location=asia-southeast1 --queue=workout-notifications

Requirements:
    - gcloud CLI authenticated
    - google-cloud-tasks>=2.15.0
"""

import argparse
import sys

from google.cloud import tasks_v2
from google.api_core import exceptions


def create_queue(
    project_id: str,
    location: str,
    queue_name: str,
    max_dispatches_per_second: float = 500,
    max_burst_size: int = 100,
    max_concurrent_dispatches: int = 1000,
    max_attempts: int = 3,
) -> None:
    """Create or update Cloud Tasks queue.

    Args:
        project_id: GCP project ID
        location: Queue location (e.g., asia-southeast1)
        queue_name: Queue name (e.g., workout-notifications)
        max_dispatches_per_second: Max tasks dispatched per second
        max_burst_size: Max tasks dispatched in a single burst
        max_concurrent_dispatches: Max concurrent task executions
        max_attempts: Max retry attempts
    """
    client = tasks_v2.CloudTasksClient()

    parent = f"projects/{project_id}/locations/{location}"
    queue_path = f"{parent}/queues/{queue_name}"

    queue = {
        "name": queue_path,
        "rate_limits": {
            "max_dispatches_per_second": max_dispatches_per_second,
            "max_burst_size": max_burst_size,
            "max_concurrent_dispatches": max_concurrent_dispatches,
        },
        "retry_config": {
            "max_attempts": max_attempts,
            "min_backoff": {"seconds": 1},
            "max_backoff": {"seconds": 3600},
            "max_doublings": 16,
        },
    }

    try:
        # Try to create the queue
        response = client.create_queue(request={"parent": parent, "queue": queue})
        print(f"Created queue: {response.name}")

    except exceptions.AlreadyExists:
        # Queue exists, update it
        print(f"Queue {queue_name} already exists, updating...")

        response = client.update_queue(request={"queue": queue})
        print(f"Updated queue: {response.name}")

    # Print queue details
    print("\nQueue configuration:")
    print(f"  Rate limits:")
    print(f"    max_dispatches_per_second: {max_dispatches_per_second}")
    print(f"    max_burst_size: {max_burst_size}")
    print(f"    max_concurrent_dispatches: {max_concurrent_dispatches}")
    print(f"  Retry config:")
    print(f"    max_attempts: {max_attempts}")
    print(f"    min_backoff: 1s")
    print(f"    max_backoff: 3600s")
    print(f"    max_doublings: 16")


def create_service_account(project_id: str) -> None:
    """Print instructions for creating service account.

    Args:
        project_id: GCP project ID
    """
    print("\n" + "=" * 60)
    print("Service Account Setup")
    print("=" * 60)
    print(
        f"""
To create a dedicated service account for Cloud Tasks, run:

# Create service account
gcloud iam service-accounts create cloudtasks-invoker \\
    --display-name="Cloud Tasks Invoker" \\
    --project={project_id}

# Grant Cloud Tasks taskRunner role
gcloud projects add-iam-policy-binding {project_id} \\
    --member="serviceAccount:cloudtasks-invoker@{project_id}.iam.gserviceaccount.com" \\
    --role="roles/cloudtasks.taskRunner"

# Grant Cloud Run invoker role (for OIDC)
gcloud projects add-iam-policy-binding {project_id} \\
    --member="serviceAccount:cloudtasks-invoker@{project_id}.iam.gserviceaccount.com" \\
    --role="roles/run.invoker"

Then set CLOUD_TASKS_SERVICE_ACCOUNT environment variable:
CLOUD_TASKS_SERVICE_ACCOUNT=cloudtasks-invoker@{project_id}.iam.gserviceaccount.com
"""
    )


def main():
    parser = argparse.ArgumentParser(
        description="Setup Cloud Tasks queue for workout notifications"
    )
    parser.add_argument(
        "--project",
        required=True,
        help="GCP project ID",
    )
    parser.add_argument(
        "--location",
        default="asia-southeast1",
        help="Queue location (default: asia-southeast1)",
    )
    parser.add_argument(
        "--queue",
        default="workout-notifications",
        help="Queue name (default: workout-notifications)",
    )
    parser.add_argument(
        "--max-dispatches",
        type=float,
        default=500,
        help="Max dispatches per second (default: 500)",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=1000,
        help="Max concurrent dispatches (default: 1000)",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Max retry attempts (default: 3)",
    )
    parser.add_argument(
        "--show-sa-setup",
        action="store_true",
        help="Show service account setup instructions",
    )

    args = parser.parse_args()

    try:
        create_queue(
            project_id=args.project,
            location=args.location,
            queue_name=args.queue,
            max_dispatches_per_second=args.max_dispatches,
            max_concurrent_dispatches=args.max_concurrent,
            max_attempts=args.max_attempts,
        )

        if args.show_sa_setup:
            create_service_account(args.project)

        print("\nQueue setup complete!")
        print(f"\nEnvironment variables to set:")
        print(f"  GCP_PROJECT_ID={args.project}")
        print(f"  CLOUD_TASKS_LOCATION={args.location}")
        print(f"  CLOUD_TASKS_QUEUE={args.queue}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
