# Phase 5: Optimization & Production Rollout

**Phase:** 5 of 5
**Duration:** 2-3 days
**Priority:** Critical
**Status:** Not Started
**Dependencies:** Phase 4 (Infrastructure Updates)

## Context

**Research Reports:**
- [GCP Microservices](./research/researcher-01-gcp-microservices.md) - Min instances tuning, cost optimization
- [Deployment Guide](../../docs/deployment-guide.md) - Current deployment procedures

**Phase 4 Deliverables:**
- 3 Cloud Run services deployed (dev environment)
- Terraform managing all infrastructure
- Jenkins pipelines operational
- Monitoring dashboards configured

## Overview

Final optimization of min/max instances, comprehensive load testing, latency validation, blue-green deployment strategy, production rollout with traffic migration, cost monitoring, and rollback procedures. Goal: Zero-downtime migration from monolith to microservices.

## Key Insights from Research

**Min Instance Tuning (Researcher-01):**
- Main API: 2 min (handle baseline CRUD traffic, <1s cold start acceptable)
- Chat AI: 1 min (warm for Q&A, <5s cold start tolerable)
- Prediction: 0 min (async workflow, 2-3s cold start acceptable)
- Cost calculation: ~$10.37/day for min instances ($311/month)

**Blue-Green Deployment:**
- Deploy new microservices architecture alongside monolith
- Split traffic gradually: 10% → 50% → 100%
- Monitor error rates and latency at each stage
- Rollback in 30 seconds if issues detected

## Requirements

**Performance Targets:**
- Main API p95 latency: < 200ms (CRUD operations)
- Chat AI p95 latency: < 3s (Q&A with AI summarization)
- Prediction p95 latency: < 10s (async workflow acceptable)
- Service-to-service p95: < 50ms

**Cost Targets:**
- Total monthly cost: < $150
- Min instances cost: ~$311/month (Main=2, Chat=1, Pred=0)
- Variable cost: $50-100/month (traffic-based scaling)
- Net savings: ~$50/month vs monolith (eliminated cold start overhead)

**Reliability:**
- 99.9% uptime (43.2 min/month downtime)
- Zero data loss during migration
- Rollback capability within 30 seconds
- All existing tests passing

## Architecture Validation

**Load Testing Scenarios:**
```
Scenario 1: Baseline CRUD (Main API)
  - 100 concurrent users
  - 1000 requests/min (user CRUD, conversation CRUD)
  - Target: p95 < 200ms

Scenario 2: Q&A Workload (Chat AI)
  - 50 concurrent users
  - 500 Q&A requests/min
  - Target: p95 < 3s

Scenario 3: Prediction Workload (Prediction)
  - 20 concurrent users
  - 100 predictions/min
  - Target: p95 < 10s

Scenario 4: Mixed Workload
  - 200 concurrent users
  - 70% CRUD, 20% Q&A, 10% Predictions
  - Target: No degradation vs monolith
```

**Traffic Migration Plan:**
```
Phase 1 (Day 1): 10% traffic to microservices
  - Monitor for 4 hours
  - Check error rates < 1%
  - Validate latency targets met

Phase 2 (Day 1-2): 50% traffic to microservices
  - Monitor for 12 hours
  - Check cost metrics
  - Validate service-to-service communication

Phase 3 (Day 2-3): 100% traffic to microservices
  - Monitor for 24 hours
  - Decommission monolith
  - Final cost analysis
```

## Implementation Steps

### 1. Load Testing Setup (Day 1)

**1.1 Create Load Testing Scripts:**
```python
# tests/load_testing/locustfile.py
"""Load testing for microservices architecture."""
from locust import HttpUser, task, between
import random

class VHealthUser(HttpUser):
    """Simulated VHealth user."""
    wait_time = between(1, 3)

    def on_start(self):
        """Login and get token."""
        response = self.client.post("/api/v1/users/login", json={
            "email": "test@example.com",
            "password": "password123"
        })
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(7)  # 70% CRUD operations
    def list_conversations(self):
        """List conversations."""
        self.client.get(
            "/api/v1/conversations/",
            headers=self.headers,
            name="/conversations (Main API)"
        )

    @task(2)  # 20% Q&A operations
    def ask_question(self):
        """Ask health question."""
        questions = [
            "What is BMI?",
            "How to lose weight?",
            "What is metabolic age?"
        ]
        self.client.post(
            "/api/v1/qa/ask",
            headers=self.headers,
            json={"question": random.choice(questions)},
            name="/qa/ask (Chat AI)"
        )

    @task(1)  # 10% Prediction operations
    def predict(self):
        """Generate health prediction."""
        self.client.post(
            "/api/v1/predict",
            headers=self.headers,
            json={
                "age": 25,
                "gender": "Male",
                "height": 1.75,
                "weight": 70,
                # ... other fields
            },
            name="/predict (Prediction)"
        )
```

**1.2 Run Load Tests:**
```bash
# Install Locust
pip install locust

# Run baseline test (monolith)
locust -f tests/load_testing/locustfile.py \
  --host https://monolith.run.app \
  --users 200 \
  --spawn-rate 10 \
  --run-time 10m \
  --html reports/monolith-baseline.html

# Run microservices test
locust -f tests/load_testing/locustfile.py \
  --host https://main-api.run.app \
  --users 200 \
  --spawn-rate 10 \
  --run-time 10m \
  --html reports/microservices.html
```

### 2. Performance Benchmarking (Day 1)

**2.1 Service-to-Service Latency Test:**
```python
# tests/benchmark_service_latency.py
"""Benchmark service-to-service latency."""
import asyncio
import time
from app.clients.chat_ai_client import chat_ai_client
from app.clients.prediction_client import prediction_client

async def benchmark_chat_ai(iterations=100):
    """Benchmark Main API → Chat AI latency."""
    latencies = []

    for _ in range(iterations):
        start = time.time()
        await chat_ai_client.ask_question("What is BMI?")
        latency = (time.time() - start) * 1000  # ms
        latencies.append(latency)

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]

    print(f"Chat AI Latency: p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")
    return p95 < 50  # Target: p95 < 50ms

async def benchmark_prediction(iterations=50):
    """Benchmark Main API → Prediction latency."""
    latencies = []

    for _ in range(iterations):
        start = time.time()
        await prediction_client.predict(test_data)
        latency = (time.time() - start) * 1000  # ms
        latencies.append(latency)

    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95)]

    print(f"Prediction Latency: p95={p95:.2f}ms")
    return p95 < 50

if __name__ == "__main__":
    asyncio.run(benchmark_chat_ai())
    asyncio.run(benchmark_prediction())
```

**2.2 Cold Start Measurement:**
```bash
# Scale down to 0 instances
gcloud run services update chat-ai-service --min-instances 0

# Wait 5 minutes for scale-down

# Measure cold start
time curl -X POST https://chat-ai-service.run.app/api/v1/qa/ask \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is BMI?"}'

# Expected: 3-5 seconds (ONNX model loading + inference)
```

### 3. Min Instance Optimization (Day 1-2)

**3.1 Cost Analysis:**
```python
# scripts/analyze_min_instances.py
"""Analyze min instance costs vs cold start impact."""

def calculate_cost(min_instances, cpu, memory_gb, idle_hours_per_day=24):
    """Calculate daily cost for min instances."""
    # Cloud Run pricing (asia-southeast1)
    cpu_price_per_sec = 0.00001708  # per vCPU-second
    mem_price_per_sec = 0.00000226  # per GB-second
    idle_price_per_sec = 0.00004  # idle instance

    seconds_per_day = idle_hours_per_day * 3600

    idle_cost = min_instances * idle_price_per_sec * seconds_per_day
    cpu_cost = min_instances * cpu * cpu_price_per_sec * seconds_per_day
    mem_cost = min_instances * memory_gb * mem_price_per_sec * seconds_per_day

    total_daily = idle_cost + cpu_cost + mem_cost
    return total_daily

# Main API (512MB, 1 vCPU)
main_api_cost_2 = calculate_cost(min_instances=2, cpu=1, memory_gb=0.5)
print(f"Main API (2 min): ${main_api_cost_2:.2f}/day")

# Chat AI (1.5GB, 1 vCPU)
chat_ai_cost_1 = calculate_cost(min_instances=1, cpu=1, memory_gb=1.5)
print(f"Chat AI (1 min): ${chat_ai_cost_1:.2f}/day")

# Prediction (768MB, 1 vCPU)
prediction_cost_0 = 0  # min=0
print(f"Prediction (0 min): ${prediction_cost_0:.2f}/day")

total = main_api_cost_2 + chat_ai_cost_1 + prediction_cost_0
print(f"\nTotal min instance cost: ${total:.2f}/day (${total * 30:.2f}/month)")
```

**3.2 Update Min Instances Based on Analysis:**
```bash
# If cold starts acceptable, reduce Chat AI to min=0
gcloud run services update chat-ai-service --min-instances 0

# Monitor cold start frequency
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=chat-ai-service AND textPayload=~\"Cold start\"" --limit 100

# If >10% requests hit cold start, increase min=1
gcloud run services update chat-ai-service --min-instances 1
```

### 4. Blue-Green Deployment Setup (Day 2)

**4.1 Deploy Microservices with Traffic Splitting:**
```bash
# Deploy microservices as "green" revision
gcloud run services update main-api-service \
  --image gcr.io/PROJECT/main-api:microservices \
  --tag green \
  --no-traffic

# Current monolith is "blue" (100% traffic)
gcloud run services update-traffic main-api-service \
  --to-revisions LATEST=0,blue=100

# Verify green is healthy
curl -f https://green---main-api-service.run.app/health

# Start traffic migration: 10% to green
gcloud run services update-traffic main-api-service \
  --to-revisions green=10,blue=90

# Monitor for 4 hours
watch -n 60 'gcloud logging read "resource.type=cloud_run_revision AND severity>=ERROR" --limit 10'

# If error rate < 1%, increase to 50%
gcloud run services update-traffic main-api-service \
  --to-revisions green=50,blue=50

# Monitor for 12 hours

# If stable, migrate to 100%
gcloud run services update-traffic main-api-service \
  --to-revisions green=100,blue=0
```

**4.2 Automated Rollback Script:**
```bash
#!/bin/bash
# scripts/rollback_to_monolith.sh
"""Automated rollback to monolith if issues detected."""

set -e

SERVICE_NAME="main-api-service"
ERROR_THRESHOLD=0.05  # 5%

# Check error rate
ERROR_RATE=$(gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME} AND severity>=ERROR" \
  --limit 1000 \
  --format json | jq -r 'length')

TOTAL_REQUESTS=$(gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=${SERVICE_NAME}" \
  --limit 1000 \
  --format json | jq -r 'length')

CURRENT_ERROR_RATE=$(echo "scale=4; $ERROR_RATE / $TOTAL_REQUESTS" | bc)

echo "Current error rate: ${CURRENT_ERROR_RATE}"

if (( $(echo "$CURRENT_ERROR_RATE > $ERROR_THRESHOLD" | bc -l) )); then
  echo "ERROR RATE EXCEEDED THRESHOLD! Rolling back to monolith..."

  # Rollback to blue (monolith)
  gcloud run services update-traffic $SERVICE_NAME \
    --to-revisions blue=100,green=0

  echo "Rollback complete. 100% traffic on monolith."

  # Send alert
  curl -X POST https://alerts.example.com/webhook \
    -H "Content-Type: application/json" \
    -d "{\"message\": \"Rollback triggered: Error rate ${CURRENT_ERROR_RATE}\"}"
else
  echo "Error rate within threshold. No rollback needed."
fi
```

### 5. Production Rollout (Day 2-3)

**5.1 Pre-Rollout Checklist:**
```bash
#!/bin/bash
# scripts/pre_rollout_checklist.sh

echo "=== Pre-Rollout Checklist ==="

# 1. All services healthy
for service in main-api-service chat-ai-service prediction-service; do
  echo "Checking $service health..."
  URL=$(gcloud run services describe $service --format='value(status.url)')
  curl -f $URL/health || exit 1
done

# 2. All tests passing
echo "Running test suite..."
pytest tests/ --cov=app --cov-report=term || exit 1

# 3. Terraform state clean
echo "Checking Terraform state..."
cd terraform
terraform plan -detailed-exitcode || exit 1

# 4. Monitoring dashboards configured
echo "Verifying monitoring setup..."
gcloud monitoring dashboards list --filter="displayName:microservices" || exit 1

# 5. Alert policies active
echo "Checking alert policies..."
gcloud alpha monitoring policies list --filter="displayName:High" || exit 1

echo "✅ All pre-rollout checks passed!"
```

**5.2 Rollout Execution:**
```bash
#!/bin/bash
# scripts/production_rollout.sh
"""Execute production rollout with monitoring."""

set -e

# Phase 1: 10% traffic (4 hours)
echo "Phase 1: Migrating 10% traffic to microservices..."
gcloud run services update-traffic main-api-service \
  --to-revisions green=10,blue=90

echo "Monitoring for 4 hours..."
sleep 14400  # 4 hours

# Check error rate
./scripts/rollback_to_monolith.sh

# Phase 2: 50% traffic (12 hours)
echo "Phase 2: Migrating 50% traffic to microservices..."
gcloud run services update-traffic main-api-service \
  --to-revisions green=50,blue=50

echo "Monitoring for 12 hours..."
sleep 43200  # 12 hours

./scripts/rollback_to_monolith.sh

# Phase 3: 100% traffic (final)
echo "Phase 3: Migrating 100% traffic to microservices..."
gcloud run services update-traffic main-api-service \
  --to-revisions green=100,blue=0

echo "Monitoring for 24 hours before decommissioning monolith..."
sleep 86400  # 24 hours

./scripts/rollback_to_monolith.sh

echo "✅ Production rollout complete!"
```

### 6. Post-Rollout Validation (Day 3)

**6.1 Cost Analysis:**
```python
# scripts/analyze_rollout_cost.py
"""Analyze cost before vs after microservices migration."""

def analyze_costs():
    """Compare costs."""
    # Before (monolith)
    monolith_cost = {
        "min_instances": 2,
        "memory": "2Gi",
        "cpu": 2,
        "monthly_cost": 400  # Estimated
    }

    # After (microservices)
    microservices_cost = {
        "main_api": {"min": 2, "memory": "512Mi", "cpu": 1, "monthly": 200},
        "chat_ai": {"min": 1, "memory": "1536Mi", "cpu": 1, "monthly": 100},
        "prediction": {"min": 0, "memory": "768Mi", "cpu": 1, "monthly": 20},
        "total_monthly": 320
    }

    savings = monolith_cost["monthly_cost"] - microservices_cost["total_monthly"]

    print(f"Monolith monthly cost: ${monolith_cost['monthly_cost']}")
    print(f"Microservices monthly cost: ${microservices_cost['total_monthly']}")
    print(f"Monthly savings: ${savings} ({savings / monolith_cost['monthly_cost'] * 100:.1f}%)")

    return savings > 0

if __name__ == "__main__":
    analyze_costs()
```

**6.2 Performance Comparison:**
```sql
-- Query: Compare latency before/after
SELECT
  DATE(timestamp) as date,
  APPROX_QUANTILES(latency_ms, 100)[OFFSET(95)] as p95_latency,
  APPROX_QUANTILES(latency_ms, 100)[OFFSET(50)] as p50_latency,
  COUNT(*) as request_count
FROM
  `project.logs.cloud_run_requests`
WHERE
  timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY date
ORDER BY date
```

**6.3 Final Validation Report:**
```markdown
# Microservices Migration Report

**Date:** 2025-11-30
**Environment:** Production

## Performance Metrics

| Metric | Monolith | Microservices | Target | Status |
|--------|----------|---------------|--------|--------|
| Main API p95 | 350ms | 180ms | <200ms | ✅ |
| Chat AI p95 | 5.2s | 2.8s | <3s | ✅ |
| Prediction p95 | 12s | 8.5s | <10s | ✅ |
| Service-to-service p95 | N/A | 35ms | <50ms | ✅ |
| Cold start (Main) | 12s | 0.8s | <1s | ✅ |
| Cold start (Chat AI) | 12s | 4.2s | <5s | ✅ |
| Cold start (Prediction) | 12s | 2.1s | <3s | ✅ |

## Cost Analysis

| Item | Monthly Cost |
|------|--------------|
| Monolith | $400 |
| Main API | $200 |
| Chat AI | $100 |
| Prediction | $20 |
| **Total Microservices** | **$320** |
| **Savings** | **$80 (20%)** |

## Reliability

- Uptime: 99.95%
- Zero data loss
- Zero failed requests during migration
- Rollback capability validated

## Recommendations

1. Monitor Chat AI cold start frequency; adjust min instances if needed
2. Consider further ONNX optimizations for Chat AI
3. Evaluate Prediction service usage patterns after 30 days
4. Decommission monolith after 7 days of stable operation
```

## Todo List

- [ ] Create load testing scripts with Locust
- [ ] Run baseline load tests on monolith
- [ ] Run load tests on microservices (dev)
- [ ] Benchmark service-to-service latency
- [ ] Measure cold start times for all services
- [ ] Analyze min instance cost vs cold start trade-off
- [ ] Update min instances based on analysis
- [ ] Create blue-green deployment scripts
- [ ] Create automated rollback script
- [ ] Create pre-rollout checklist script
- [ ] Execute Phase 1: 10% traffic migration
- [ ] Monitor Phase 1 for 4 hours
- [ ] Execute Phase 2: 50% traffic migration
- [ ] Monitor Phase 2 for 12 hours
- [ ] Execute Phase 3: 100% traffic migration
- [ ] Monitor Phase 3 for 24 hours
- [ ] Run cost analysis (before vs after)
- [ ] Run performance comparison (before vs after)
- [ ] Create final validation report
- [ ] Decommission monolith (after 7 days stable)
- [ ] Update deployment guide with microservices procedures

## Success Criteria

**All Targets Met:**
- ✅ Main API cold start < 1s
- ✅ Chat AI cold start < 5s
- ✅ Prediction cold start < 3s
- ✅ Service-to-service latency < 50ms
- ✅ Total cost < $150/month
- ✅ Zero downtime during migration
- ✅ All tests passing

**Operational:**
- Blue-green deployment successful
- Rollback capability validated
- Monitoring dashboards operational
- Alert policies triggering correctly

## Risk Assessment

**Traffic Migration Failure:**
- Risk: High error rates during traffic split
- Mitigation: Gradual rollout (10% → 50% → 100%)
- Rollback: Automated script (30-second rollback)

**Cost Overruns:**
- Risk: Variable costs exceed budget
- Mitigation: Set max-instances conservatively; monitor daily
- Action: Adjust min/max instances if needed

**Cold Start Impact:**
- Risk: User experience degraded by cold starts
- Mitigation: Min instances for critical services
- Action: Increase min instances if cold start rate >10%

## Security Considerations

**Production Secrets:**
- All secrets in Secret Manager
- Service accounts use IAM roles (no API keys)
- Audit logs enabled for all services

**Network Security:**
- Direct VPC Egress for private communication
- Cloud SQL/Redis accessible only via private IPs
- HTTPS enforced for all external traffic

## Next Steps

**After Phase 5 Completion:**
- Monitor costs daily for first month
- Optimize min instances based on usage patterns
- Plan Phase 6: Additional microservices (if needed)
- Decommission monolith infrastructure
- Update documentation with final architecture
