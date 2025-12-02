#!/usr/bin/env python3
"""
Load test lazy loading under concurrent requests.
Simulates real-world traffic patterns.

Usage:
    python scripts/load_test_lazy_loading.py http://localhost:8080
    python scripts/load_test_lazy_loading.py https://test.vhealth.io.vn
"""
import asyncio
import sys
import time
from typing import Dict, List

import httpx


async def send_request(client: httpx.AsyncClient, question: str, delay: float = 0) -> Dict:
    """
    Send single Q&A request.

    Args:
        client: HTTP client
        question: Question to ask
        delay: Delay before sending request (for staggered requests)

    Returns:
        Result dict with status and latency
    """
    await asyncio.sleep(delay)
    start = time.time()

    try:
        response = await client.post(
            "/api/v1/qa/ask",
            json={"question": question, "threshold": 0.55, "top_k": 7},
            timeout=30.0,
        )
        elapsed = time.time() - start

        return {
            "status": response.status_code,
            "latency_ms": round(elapsed * 1000, 2),
            "success": response.status_code == 200,
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "status": 0,
            "latency_ms": round(elapsed * 1000, 2),
            "success": False,
            "error": str(e),
        }


async def check_health(url: str) -> Dict:
    """Check Q&A service health status."""
    async with httpx.AsyncClient(base_url=url) as client:
        try:
            response = await client.get("/api/v1/qa/health", timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                return {
                    "status": data.get("status"),
                    "model_loaded": data.get("model_loaded"),
                    "message": data.get("message"),
                }
            return {"status": "error", "code": response.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}


async def load_test(url: str, concurrent_requests: int = 10):
    """
    Simulate concurrent first requests.

    Args:
        url: Base URL of the service
        concurrent_requests: Number of concurrent requests to send
    """
    print(f"🔍 Testing lazy loading at: {url}")
    print(f"📊 Concurrent requests: {concurrent_requests}\n")

    # Check health before testing
    print("1️⃣  Checking service health...")
    health = await check_health(url)
    print(f"   Status: {health.get('status')}")
    print(f"   Model loaded: {health.get('model_loaded')}")
    print(f"   Message: {health.get('message', 'N/A')}\n")

    # Test questions (Vietnamese health questions)
    questions = [
        "Làm thế nào để giảm cân?",
        "Cách phòng ngừa bệnh tiểu đường?",
        "Tôi nên ăn gì để tăng cường miễn dịch?",
        "Làm thế nào để cải thiện giấc ngủ?",
        "Cách giảm stress hiệu quả?",
        "Tập thể dục như thế nào là tốt?",
        "Làm sao để giảm cholesterol?",
        "Cách phòng chống bệnh tim mạch?",
        "Nên ăn bao nhiêu calo mỗi ngày?",
        "Làm thế nào để tăng cơ bắp?",
    ]

    async with httpx.AsyncClient(base_url=url, timeout=30.0) as client:
        # Send concurrent requests (staggered by 100ms)
        print(f"2️⃣  Sending {concurrent_requests} concurrent requests...")
        tasks = [
            send_request(
                client, questions[i % len(questions)], delay=i * 0.1
            )
            for i in range(concurrent_requests)
        ]

        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Analyze results
        successes = [r for r in results if r["success"]]
        failures = [r for r in results if not r["success"]]
        latencies = [r["latency_ms"] for r in successes]

        print(f"   Total time: {total_time:.2f}s")
        print(f"   Success: {len(successes)}/{concurrent_requests}")
        print(f"   Failures: {len(failures)}\n")

        if latencies:
            print("3️⃣  Latency Statistics:")
            print(f"   Min: {min(latencies):.2f}ms")
            print(f"   Max: {max(latencies):.2f}ms")
            print(f"   Avg: {sum(latencies) / len(latencies):.2f}ms")
            print(f"   Median: {sorted(latencies)[len(latencies) // 2]:.2f}ms")

            if len(latencies) >= 10:
                p95_idx = int(len(latencies) * 0.95)
                print(f"   P95: {sorted(latencies)[p95_idx]:.2f}ms\n")

            # Analyze first few requests (lazy load behavior)
            print("4️⃣  First Request Analysis (Lazy Load):")
            print(f"   Request 1: {results[0]['latency_ms']:.2f}ms (expected: ~5000ms)")
            if len(results) > 1:
                print(f"   Request 2: {results[1]['latency_ms']:.2f}ms (expected: <100ms)")
            if len(results) > 2:
                print(f"   Request 3: {results[2]['latency_ms']:.2f}ms (expected: <100ms)")

            # Check if first request shows lazy loading pattern
            first_latency = results[0]["latency_ms"]
            if first_latency > 3000:
                print(f"\n   ✅ Lazy loading detected (first request: {first_latency:.2f}ms)")
            else:
                print(f"\n   ⚠️  Model may already be loaded (first request: {first_latency:.2f}ms)")

        if failures:
            print("\n❌ Failures:")
            for i, failure in enumerate(failures[:5], 1):  # Show first 5
                print(f"   {i}. Status: {failure['status']}, Error: {failure.get('error', 'N/A')}")

        # Check health after testing
        print("\n5️⃣  Checking service health after load test...")
        health_after = await check_health(url)
        print(f"   Status: {health_after.get('status')}")
        print(f"   Model loaded: {health_after.get('model_loaded')}")
        print(f"   Message: {health_after.get('message', 'N/A')}")

        # Summary
        print("\n📈 Summary:")
        print(f"   Total requests: {concurrent_requests}")
        print(f"   Successful: {len(successes)} ({len(successes)/concurrent_requests*100:.1f}%)")
        print(f"   Failed: {len(failures)} ({len(failures)/concurrent_requests*100:.1f}%)")
        if latencies:
            print(f"   Avg latency: {sum(latencies)/len(latencies):.2f}ms")
            print(f"   Total time: {total_time:.2f}s")
            print(f"   Throughput: {len(successes)/total_time:.2f} req/s")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/load_test_lazy_loading.py <url>")
        print("\nExamples:")
        print("  python scripts/load_test_lazy_loading.py http://localhost:8080")
        print("  python scripts/load_test_lazy_loading.py https://test.vhealth.io.vn")
        sys.exit(1)

    url = sys.argv[1]
    concurrent_requests = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    asyncio.run(load_test(url, concurrent_requests))


if __name__ == "__main__":
    main()
