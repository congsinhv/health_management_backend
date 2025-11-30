# VHealth Chat AI Service

Standalone microservice for Vietnamese health question answering with SBERT and OpenAI integration.

## Features

- **ONNX-Optimized SBERT**: 2-5x faster inference with Vietnamese support
- **OpenAI Integration**: Response summarization with GPT-4o-mini
- **Streaming Support**: Server-sent events for real-time responses
- **Service Communication**: IAM-based authentication with Main API
- **Caching**: Optional Redis caching for performance
- **Health Monitoring**: Comprehensive health checks and metrics

## Architecture

```
├── app/
│   ├── main.py              # FastAPI application entrypoint
│   ├── config.py             # Service configuration
│   ├── api/
│   │   └── qa.py          # Q&A API endpoints
│   ├── services/
│   │   └── qa/            # Core QA service logic
│   ├── core/
│   │   └── shared/         # Symlink to main app/core/shared
│   └── schemas/
│       └── qa.py            # Pydantic models
├── tests/
├── models/                  # Model files and cache
├── Dockerfile
└── requirements.txt
```

## Performance

- **Model Loading**: Pre-load at startup eliminates cold start
- **ONNX Speed**: 2-5x faster inference vs PyTorch
- **Int8 Quantization**: 30-40% additional speedup
- **Cold Start**: Target <5s (vs 10-15s monolith)
- **Memory**: Target 1.5GB (vs 2GB monolith)
- **Latency**: <50ms service-to-service communication

## Deployment

Deployed to Google Cloud Run with:
- 1 minimum instance ($3.46/day)
- Maximum 10 instances for scaling
- Direct VPC egress for database access
- IAM-based service authentication
- Environment-based configuration

## Usage

### Local Development
```bash
cd chat_ai_service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8081
```

### Production
```bash
gcloud run services add-iam-policy-binding \
    chat-ai-service \
    --member=serviceAccount:main-api-service@PROJECT.iam.gserviceaccount.com \
    --role=roles/run.invoker
```

## Monitoring

- **Health Check**: `/health` endpoint
- **Metrics**: OpenTelemetry integration
- **Logging**: Structured JSON logs
- **Error Tracking**: Comprehensive exception handling

## API Endpoints

- `POST /api/v1/qa/ask` - Ask question (sync)
- `POST /api/v1/qa/ask/stream` - Ask question (streaming)
- `GET /api/v1/qa/health` - Service health check
- `GET /api/v1/qa/stats` - Usage statistics

## Configuration

Environment variables:
- `OPENAI_API_KEY` - OpenAI API key
- `ENABLE_ONNX` - Use ONNX backend (default: true)
- `ENABLE_QUANTIZATION` - Use int8 quantization (default: true)
- `QA_MODEL_PATH` - Path to SBERT model
- `REDIS_URL` - Optional Redis cache
- `LOG_LEVEL` - Logging level (default: INFO)