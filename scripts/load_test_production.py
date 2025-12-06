"""
Production-grade load test for Q&A service.
Tests memory stability under concurrent requests.

Usage:
    python scripts/load_test_production.py <BASE_URL> <AUTH_TOKEN>

Example:
    TOKEN=$(curl -s -X POST https://test.vhealth.io.vn/api/v1/auth/login \
      -H "Content-Type: application/json" \
      -d '{"email":"test@example.com","password":"password"}' \
      | jq -r '.access_token')

    python scripts/load_test_production.py \
      https://test.vhealth.io.vn \
      "$TOKEN"
"""
import asyncio
import time
import statistics
from typing import List, Dict
from httpx import AsyncClient


class LoadTester:
    """Load tester for Q&A service."""

    def __init__(self, base_url: str, auth_token: str):
        self.base_url = base_url
        self.auth_token = auth_token
        self.results = []

    async def send_request(self, question: str) -> Dict:
        """Send single Q&A request and measure latency."""
        async with AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {self.auth_token}"}

            start = time.time()
            try:
                response = await client.post(
                    "/api/v1/qa/ask",
                    json={"question": question, "threshold": 0.55, "top_k": 7},
                    headers=headers,
                )
                elapsed_ms = (time.time() - start) * 1000

                return {
                    "status": response.status_code,
                    "latency_ms": round(elapsed_ms, 2),
                    "success": response.status_code == 200,
                    "question": question,
                }
            except Exception as e:
                return {
                    "status": 0,
                    "latency_ms": 0,
                    "success": False,
                    "error": str(e),
                    "question": question,
                }

    async def run_load_test(
        self,
        questions: List[str],
        concurrent_users: int = 10,
        requests_per_user: int = 5,
    ):
        """
        Run load test with multiple concurrent users.

        Args:
            questions: List of test questions
            concurrent_users: Number of concurrent users
            requests_per_user: Requests each user sends
        """
        print(f"Starting load test:")
        print(f"  Concurrent users: {concurrent_users}")
        print(f"  Requests per user: {requests_per_user}")
        print(f"  Total requests: {concurrent_users * requests_per_user}")
        print(f"  Target URL: {self.base_url}")

        tasks = []
        for user_id in range(concurrent_users):
            for req_id in range(requests_per_user):
                # Rotate through questions
                question = questions[
                    (user_id * requests_per_user + req_id) % len(questions)
                ]
                tasks.append(self.send_request(question))

        # Execute all requests concurrently
        start = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start

        # Analyze results
        self.results = results
        self._print_results(total_time)

    def _print_results(self, total_time: float):
        """Print load test results."""
        successful = [r for r in self.results if r["success"]]
        failed = [r for r in self.results if not r["success"]]

        latencies = [r["latency_ms"] for r in successful]

        print("\n" + "=" * 60)
        print("LOAD TEST RESULTS")
        print("=" * 60)
        print(f"Total requests: {len(self.results)}")
        print(f"Successful: {len(successful)}")
        print(f"Failed: {len(failed)}")
        print(f"Success rate: {len(successful)/len(self.results)*100:.2f}%")
        print(f"Total time: {total_time:.2f}s")
        print(f"Requests/sec: {len(self.results)/total_time:.2f}")

        if latencies:
            print(f"\nLatency statistics:")
            print(f"  Min: {min(latencies):.2f}ms")
            print(f"  Max: {max(latencies):.2f}ms")
            print(f"  Mean: {statistics.mean(latencies):.2f}ms")
            print(f"  Median: {statistics.median(latencies):.2f}ms")
            print(f"  P95: {sorted(latencies)[int(len(latencies)*0.95)]:.2f}ms")
            print(f"  P99: {sorted(latencies)[int(len(latencies)*0.99)]:.2f}ms")

        if failed:
            print(f"\nFailed requests:")
            for r in failed[:5]:  # Show first 5 failures
                print(f"  {r['question'][:50]}: {r.get('error', 'Unknown error')}")

        print("=" * 60)


# Vietnamese test questions
TEST_QUESTIONS = [
    "Làm thế nào để giảm cân hiệu quả?",
    "Triệu chứng của bệnh tiểu đường là gì?",
    "Chế độ ăn cho người huyết áp cao",
    "Cách phòng ngừa bệnh tim mạch",
    "Tác dụng của vitamin C với sức khỏe",
    "Làm thế nào để tăng cường hệ miễn dịch?",
    "Nguyên nhân gây bệnh trào ngược dạ dày",
    "Cách điều trị viêm họng tại nhà",
    "Chế độ ăn cho người bị gout",
    "Triệu chứng của bệnh xơ gan",
]


async def main():
    import sys

    if len(sys.argv) < 3:
        print("Usage: python load_test_production.py <BASE_URL> <AUTH_TOKEN>")
        sys.exit(1)

    base_url = sys.argv[1]
    auth_token = sys.argv[2]

    tester = LoadTester(base_url, auth_token)

    # Test scenarios
    print("Scenario 1: Light load (5 concurrent users)")
    await tester.run_load_test(TEST_QUESTIONS, concurrent_users=5, requests_per_user=10)
    await asyncio.sleep(5)

    print("\nScenario 2: Medium load (15 concurrent users)")
    await tester.run_load_test(
        TEST_QUESTIONS, concurrent_users=15, requests_per_user=10
    )
    await asyncio.sleep(5)

    print("\nScenario 3: Heavy load (30 concurrent users)")
    await tester.run_load_test(TEST_QUESTIONS, concurrent_users=30, requests_per_user=5)


if __name__ == "__main__":
    asyncio.run(main())
