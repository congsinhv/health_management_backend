"""Test Cloud Run cold-start timing."""
import argparse
import time
import subprocess
import json


def scale_down_to_zero(project: str, service: str, region: str):
    """Scale service to 0 instances."""
    print(f"Scaling {service} to 0 instances...")
    cmd = [
        "gcloud",
        "run",
        "services",
        "update",
        service,
        f"--project={project}",
        f"--region={region}",
        "--min-instances=0",
        "--quiet",
    ]
    subprocess.run(cmd, check=True)
    print("Waiting 5min for scale-down...")
    time.sleep(300)  # Wait 5min


def measure_cold_start(url: str) -> float:
    """Measure cold-start latency."""
    import httpx

    print(f"Sending cold-start request to {url}...")
    start = time.time()

    try:
        response = httpx.get(f"{url}/api/v1/qa/health", timeout=60.0)
        duration = time.time() - start

        if response.status_code == 200:
            print(f"Health check passed in {duration:.2f}s")
            return duration
        else:
            print(f"Health check failed: HTTP {response.status_code}")
            return -1
    except Exception as e:
        print(f"Request failed: {e}")
        return -1


def restore_min_instances(project: str, service: str, region: str, min_instances: int):
    """Restore min-instances setting."""
    print(f"Restoring min-instances={min_instances}...")
    cmd = [
        "gcloud",
        "run",
        "services",
        "update",
        service,
        f"--project={project}",
        f"--region={region}",
        f"--min-instances={min_instances}",
        "--quiet",
    ]
    subprocess.run(cmd, check=True)


def main():
    parser = argparse.ArgumentParser(description="Test cold-start timing")
    parser.add_argument("project", help="GCP project ID")
    parser.add_argument("service", help="Cloud Run service name")
    parser.add_argument("--region", default="asia-southeast1")
    parser.add_argument("--url", required=True, help="Service URL")
    parser.add_argument("--threshold", type=float, default=1.0, help="Max cold-start (s)")
    parser.add_argument("--restore-min-instances", type=int, default=1)
    args = parser.parse_args()

    try:
        # Scale down
        scale_down_to_zero(args.project, args.service, args.region)

        # Measure cold-start
        cold_start_time = measure_cold_start(args.url)

        # Restore
        restore_min_instances(
            args.project, args.service, args.region, args.restore_min_instances
        )

        # Validate
        if cold_start_time < 0:
            print("❌ Cold-start request failed")
            exit(1)

        if cold_start_time > args.threshold:
            print(
                f"❌ Cold-start too slow: {cold_start_time:.2f}s > {args.threshold}s"
            )
            exit(1)

        print(f"✅ Cold-start passed: {cold_start_time:.2f}s < {args.threshold}s")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        # Restore min-instances on error
        restore_min_instances(
            args.project, args.service, args.region, args.restore_min_instances
        )
        exit(1)


if __name__ == "__main__":
    main()