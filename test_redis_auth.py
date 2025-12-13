import asyncio
import redis.asyncio as redis
import ssl

async def test_redis_auth():
    # GCP Memorystore details
    host = "10.34.0.3"
    port = 6378
    password = "vhealth-cache-test-auth-string"
    
    # SSL options for GCP Memorystore
    ssl_kwargs = {
        "ssl": True,
        "ssl_cert_reqs": ssl.CERT_NONE,
        "ssl_check_hostname": False,
    }
    
    print(f"Testing Redis connection to {host}:{port}")
    print(f"Password: {'***' if password else 'None'}")
    
    try:
        # Method 1: Using password parameter
        print("\n--- Method 1: Password parameter ---")
        client1 = redis.Redis(
            host=host,
            port=port,
            password=password,
            **ssl_kwargs
        )
        result = await client1.ping()
        print(f"✓ Method 1 success: {result}")
        await client1.close()
        
    except Exception as e:
        print(f"✗ Method 1 failed: {e}")
    
    try:
        # Method 2: Using URL format
        print("\n--- Method 2: URL format ---")
        redis_url = f"rediss://:{password}@{host}:{port}/0"
        print(f"URL: rediss://:***@{host}:{port}/0")
        client2 = redis.from_url(
            redis_url,
            **ssl_kwargs
        )
        result = await client2.ping()
        print(f"✓ Method 2 success: {result}")
        await client2.close()
        
    except Exception as e:
        print(f"✗ Method 2 failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_redis_auth())
