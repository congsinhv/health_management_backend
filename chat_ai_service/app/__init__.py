"""VHealth Chat AI Service - Standalone microservice for Vietnamese health Q&A.

This service provides:
- SBERT-based question answering with ONNX optimization
- OpenAI-powered response summarization
- Server-sent events for streaming responses
- Service-to-service communication with IAM auth
- Health monitoring and metrics

FastAPI application with async processing.
"""
