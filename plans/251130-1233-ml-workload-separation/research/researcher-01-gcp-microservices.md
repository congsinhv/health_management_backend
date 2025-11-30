# GCP Cloud Run Microservices Architecture Research
**Date:** 2025-11-30 | **Region:** asia-southeast1

## Executive Summary

Cloud Run supports production-grade microservices via IAM-based service-to-service auth, Direct VPC Egress (preferred over VPC Connectors), and intelligent auto-scaling. For FastAPI workloads, use service accounts + IAM roles for auth, Direct VPC Egress for networking, and tuned min/max instances for cost control.

---

## 1. Service-to-Service Authentication

### Recommended Approach: IAM Identity Tokens

**Method:** Service Account + OpenID Connect (OIDC)

- Each service has dedicated user-managed service account
- Source service retrieves identity token from Compute Metadata Server
- Token added to request header: `Authorization: Bearer ID_TOKEN`
- Destination service validates token via IAM Invoker role

**Implementation:**
```bash
# Grant calling service invoker permission on target
gcloud run services add-iam-policy-binding TARGET_SERVICE \
  --member=serviceAccount:CALLER_SA@PROJECT.iam.gserviceaccount.com \
  --role=roles/run.invoker
```

**Advantages:**
- No API key rotation burden
- Automatic token refresh (1hr expiry)
- Audit trail via Cloud Audit Logs
- Fine-grained IAM control

**Trade-off:** Token generation adds ~5-10ms per request (cached by metadata server for 5min).

### API Keys (Not Recommended for Service-to-Service)

Only use for external third-party integrations; avoid for internal services.

---

## 2. Service Discovery & Networking

### DNS Service Discovery (Built-in)

**Cloud Run FQDN:** `SERVICE_NAME.REGION.run.app` (publicly routable)

For private communication, use VPC networking to route through private IP space.

### Network Architecture Comparison

| Feature | Direct VPC Egress | VPC Connector | Public URL |
|---------|------------------|---------------|-----------|
| Latency | ✓ Lower (~2-5ms) | Higher (extra hop) | Highest |
| Throughput | ✓ Better | Limited | Baseline |
| Cost | ✓ Lower | Monthly fee | No extra cost |
| Setup | Simple | Complex | None |
| **Recommendation** | ✓ **Preferred for 2024+** | Legacy | Internal only |

### Configuration (Direct VPC Egress)

```yaml
# Cloud Run service with Direct VPC Egress
gcloud run deploy SERVICE \
  --network=NETWORK \
  --subnet=SUBNET \
  --network-interface=eni0
```

**Requirement:** Enable Compute Engine API and configure VPC with Custom Routes.

---

## 3. Connection Management

### VPC Egress Routing

**Private IP Services:** Cloud SQL, Memorystore Redis, GKE clusters

1. Configure Cloud Run service to route traffic through VPC
2. Use Private Google Access for internal APIs
3. Cloud SQL Proxy connection pooling (recommended)
4. Redis connection pooling: 10-20 connections per service instance

### Connection Pooling Best Practices

**asyncpg (PostgreSQL):**
```python
# app/db/database.py
pool = await asyncpg.create_pool(
    DSN,
    min_size=5,
    max_size=20,
    timeout=30.0,
    command_timeout=30.0
)
```

**Redis (aioredis):**
```python
redis_pool = aioredis.ConnectionPool.from_url(
    url,
    max_connections=15,
    socket_keepalive=True
)
```

**Rationale:** Reusing connections reduces handshake overhead; sized to instance concurrency.

---

## 4. Performance Benchmarks

### Inter-Service Latency (asia-southeast1)

- **Direct VPC Egress:** 2-5ms p95 (Cloud Run → Cloud SQL/Redis in same VPC)
- **VPC Connector:** 8-15ms p95 (extra network hop penalty)
- **Public URL:** 15-30ms p95 (Cloud Run → Cloud Run via external LB)

### Factors Affecting Latency

1. **Cold Starts:** 500ms-1s (Python startup overhead); mitigate with min-instances > 0
2. **Instance Concurrency:** Default 80 requests/instance; tune based on CPU/memory usage
3. **Gen2 Runtime:** ~10% faster networking than Gen1
4. **Packet Loss:** Gen2 has better recovery; use Gen2 for high-packet-loss networks

### Optimization Techniques

- Enable connection pooling (50% latency reduction)
- Reuse HTTP clients across requests
- Set `GRPC_PYTHON_BUILD_WITH_CYTHON=1` for Python gRPC
- Use cached DNS lookups (avoid DNS lookups per request)

---

## 5. Cost Optimization Strategy

### Min/Max Instance Configuration

**Recommended for FastAPI ML Workloads:**

```bash
# Core API service
gcloud run deploy api-service \
  --min-instances=2 \
  --max-instances=50 \
  --memory=2Gi \
  --cpu=2 \
  --concurrency=80

# ML worker (async processing)
gcloud run deploy ml-worker \
  --min-instances=1 \
  --max-instances=20 \
  --memory=4Gi \
  --cpu=2 \
  --concurrency=1  # ML model inference needs dedicated CPU
```

### Cost Calculation (asia-southeast1)

**API Service (2 min, 50 max):**
- Min instances: 2 × $0.00004/sec × 86400 = ~$6.91/day
- Variable CPU: $0.00001708/vcpu-sec
- Memory: $0.00000226/GB-sec

**ML Worker (1 min, 20 max):**
- Min instance: 1 × $0.00004/sec × 86400 = ~$3.46/day
- Scales on-demand for batch jobs

**Savings:** Setting min=0 for non-critical services saves 100% idle cost; trade-off: cold starts.

### Scaling Policies

**Autoscaler Target:** 60% concurrency utilization over 60-second window

For ML workloads expecting spiky traffic:
- Set `max-instances` conservatively (e.g., 20) to prevent runaway costs
- Use Cloud Tasks or Pub/Sub for async processing to decouple request handling
- Implement backpressure (queue) rather than scaling infinitely

---

## Key Recommendations for Health Management System

### Architecture

1. **API Service:** 2-4 min instances (handle user requests, low latency requirement)
2. **ML Inference Service:** 1 min instance (async worker, batch processing)
3. **PDF Service:** 0 min instances (triggered on-demand, can tolerate cold starts)

### Authentication

- Use service account identities (not API keys)
- Avoid token caching; Metadata Server handles it transparently
- Rotate service account keys quarterly (optional; OIDC doesn't require it)

### Networking

- **Direct VPC Egress** for Cloud SQL + Redis (asia-southeast1)
- Custom VPC routes: ensure private IPs for internal services
- Keep default concurrency at 80 (suitable for FastAPI)

### Monitoring

- CloudTrace for latency profiling (identify bottlenecks)
- CloudMonitoring dashboards for min-instance cost trends
- Set alerts: Cold start rate > 10%, p95 latency > 500ms

---

## Unresolved Questions

1. Should ML model inference run as separate service or integrated with API? (Trade-off: isolation vs. latency)
2. What's acceptable cold start latency for PDF generation? (Currently 2-3s; async Pub/Sub recommended if < 500ms required)
3. Redis caching for conversation embeddings—invalidation strategy? (TTL-based or event-driven?)

---

## Sources

- [Authenticating service-to-service | Cloud Run](https://cloud.google.com/run/docs/authenticating/service-to-service)
- [Introduction to service identity | Cloud Run](https://cloud.google.com/run/docs/securing/service-identity)
- [Best practices for Cloud Run networking](https://cloud.google.com/run/docs/configuring/networking-best-practices)
- [Comparing Direct VPC egress and VPC connectors](https://cloud.google.com/run/docs/configuring/connecting-vpc)
- [Private networking and Cloud Run](https://cloud.google.com/run/docs/securing/private-networking)
- [How we optimized Cloud Run Networking with Direct VPC Egress](https://eagleeye.com/blog/how-we-optimized-cloud-run-networking-with-direct-vpc-egress)
- [About instance autoscaling in Cloud Run services](https://cloud.google.com/run/docs/about-instance-autoscaling)
- [Set minimum instances for services](https://cloud.google.com/run/docs/configuring/min-instances)
- [Google Cloud Run: Pricing and Cost Optimization](https://www.prosperops.com/blog/google-cloud-run-pricing-and-cost-optimization/)
- [Cloud Run / GKE & Istio: network latency comparison](https://medium.com/google-cloud/cloud-run-gke-istio-network-latency-comparison-60f9599a50bb)
