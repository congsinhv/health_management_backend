"""Smoke tests after deployment."""
import argparse
import httpx
import asyncio


async def test_health_endpoint(url: str) -> bool:
    """Test /health endpoint."""
    print("Testing /health endpoint...")
    try:
        # Validate URL format
        if not url.startswith(('http://', 'https://')):
            print("  ❌ Invalid URL format")
            return False

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/api/v1/qa/health", timeout=10.0)
            if response.status_code == 200:
                data = response.json()
                print(f"  Status: {data.get('status')}")
                return data.get("status") == "healthy"
            else:
                print(f"  ❌ HTTP {response.status_code}")
                return False
    except httpx.RequestError as e:
        print(f"  ❌ Request failed: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return False


async def test_qa_endpoint(url: str, token: str) -> bool:
    """Test Q&A endpoint."""
    print("Testing /qa/ask endpoint...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{url}/api/v1/qa/ask",
                json={"question": "Làm thế nào để giảm cân?", "threshold": 0.55},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30.0,
            )
            if response.status_code == 200:
                data = response.json()
                has_answers = len(data.get("answers", [])) > 0
                print(f"  Answers found: {has_answers}")
                return has_answers
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


async def test_cache_stats(url: str, admin_token: str) -> bool:
    """Test cache stats endpoint."""
    print("Testing /cache/stats endpoint...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{url}/api/v1/cache/stats",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json()
                print(f"  Cache enabled: {data.get('enabled')}")
                return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Deployment smoke tests")
    parser.add_argument("url", help="API base URL")
    parser.add_argument("--token", help="Auth token")
    parser.add_argument("--admin-token", help="Admin token")
    args = parser.parse_args()

    # Validate URL
    if not args.url.startswith(('http://', 'https://')):
        print("❌ Invalid URL format. Must start with http:// or https://")
        exit(1)

    print("=== Deployment Smoke Tests ===\n")

    results = []

    # Health check
    results.append(await test_health_endpoint(args.url))

    # Q&A endpoint (if token provided)
    if args.token:
        results.append(await test_qa_endpoint(args.url, args.token))

    # Cache stats (if admin token provided)
    if args.admin_token:
        results.append(await test_cache_stats(args.url, args.admin_token))

    # Summary
    passed = sum(results)
    total = len(results)

    print(f"\n=== Results: {passed}/{total} passed ===")

    if passed < total:
        print("❌ Some tests failed")
        exit(1)

    print("✅ All smoke tests passed")


if __name__ == "__main__":
    asyncio.run(main())