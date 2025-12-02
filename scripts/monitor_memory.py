"""
Monitor Cloud Run memory usage in real-time.
Alerts if memory exceeds threshold.

NOTE: Requires google-cloud-monitoring package (production environment only).
      Install: pip install google-cloud-monitoring

Usage:
    python scripts/monitor_memory.py <PROJECT_ID> <SERVICE_NAME> [THRESHOLD]

Example:
    python scripts/monitor_memory.py vhealth-test vhealth-backend-test 85
"""
import time

try:
    from google.cloud import monitoring_v3
except ImportError:
    print("ERROR: google-cloud-monitoring package not installed")
    print("Install: pip install google-cloud-monitoring")
    exit(1)


def get_memory_usage(project_id: str, service_name: str):
    """Get current memory usage from Cloud Monitoring."""
    client = monitoring_v3.MetricServiceClient()
    project_name = f"projects/{project_id}"

    # Query last 5 minutes
    now = time.time()
    seconds = int(now)
    nanos = int((now - seconds) * 10**9)
    interval = monitoring_v3.TimeInterval(
        {
            "end_time": {"seconds": seconds, "nanos": nanos},
            "start_time": {"seconds": (seconds - 300), "nanos": nanos},
        }
    )

    # Build query
    results = client.list_time_series(
        request={
            "name": project_name,
            "filter": f'metric.type="run.googleapis.com/container/memory/utilizations" '
            f'resource.labels.service_name="{service_name}"',
            "interval": interval,
            "view": monitoring_v3.ListTimeSeriesRequest.TimeSeriesView.FULL,
        }
    )

    # Get latest value
    for result in results:
        for point in result.points:
            memory_percent = point.value.double_value * 100
            return memory_percent

    return None


def monitor_continuously(project_id: str, service_name: str, threshold: float = 90.0):
    """Monitor memory usage continuously."""
    print(f"Monitoring {service_name} in {project_id}")
    print(f"Alert threshold: {threshold}%")
    print("=" * 60)

    while True:
        memory = get_memory_usage(project_id, service_name)

        if memory is not None:
            status = "🔴 ALERT" if memory > threshold else "✅ OK"
            print(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} - Memory: {memory:.2f}% {status}"
            )

            if memory > threshold:
                print(f"  ⚠️  Memory usage exceeds {threshold}%!")

        time.sleep(30)  # Check every 30 seconds


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python monitor_memory.py <PROJECT_ID> <SERVICE_NAME> [THRESHOLD]")
        print("\nExample:")
        print("  python monitor_memory.py vhealth-test vhealth-backend-test 85")
        sys.exit(1)

    project_id = sys.argv[1]
    service_name = sys.argv[2]
    threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 85.0

    monitor_continuously(project_id, service_name, threshold)
