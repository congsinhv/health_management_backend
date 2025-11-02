FROM python:3.13-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=5

RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash appuser
USER appuser
WORKDIR /home/appuser

COPY requirements-prod.txt .

# Install torch separately first with aggressive retry settings to handle large download
# Using CPU-only version to reduce image size from ~3.5GB to ~200MB
RUN --mount=type=cache,target=/home/appuser/.cache/pip,uid=1000,gid=1000 \
    pip install --user \
    --retries 10 \
    --timeout 300 \
    --index-url https://download.pytorch.org/whl/cpu \
    torch==2.9.0

# Install remaining dependencies
RUN --mount=type=cache,target=/home/appuser/.cache/pip,uid=1000,gid=1000 \
    pip install --user \
    --retries 5 \
    --timeout 300 \
    -r requirements-prod.txt

FROM python:3.13-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/home/appuser/.local/bin:$PATH" \
    PORT=8080 \
    QA_MODEL_PATH=/home/appuser/.cache/models/vietnamese-sbert \
    QA_DATA_PATH=/home/appuser/.cache/data/data.xlsx \
    QA_VOCAB_PATH=/home/appuser/.cache/data/tuvung.txt

RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash appuser

COPY --from=builder /home/appuser/.local /home/appuser/.local

USER appuser
WORKDIR /home/appuser/app

# Create cache directories for Q&A models and data
RUN mkdir -p /home/appuser/.cache/models/vietnamese-sbert && \
    mkdir -p /home/appuser/.cache/data

COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser scripts/migrations/ ./migrations/

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')" || exit 1

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]

FROM production AS development

USER root
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]
