ARG BASE_IMAGE
FROM ${BASE_IMAGE:-python:3.13-slim} AS production

# Ensure we're running as root and install system dependencies required by WeasyPrint
USER root
RUN mkdir -p /var/lib/apt/lists/partial && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    libglib2.0-0 \
    shared-mime-info \
    fonts-dejavu-core \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

# Create appuser if it doesn't exist (base image may already have it)
RUN getent group appuser >/dev/null 2>&1 || groupadd appuser && \
    getent passwd appuser >/dev/null 2>&1 || useradd -g appuser -m appuser

# Install Python dependencies
COPY requirements.txt .
# Install all dependencies including PyTorch CPU version
RUN pip install --no-cache-dir \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    -r requirements.txt

# Set working directory first
WORKDIR /app

# Copy application code with correct structure
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser scripts/migrations/ ./migrations/
# Ensure the font file is copied and available
COPY --chown=appuser:appuser app/static/fonts/NotoSans-Regular.ttf ./app/static/fonts/

# Add app directory to Python path
ENV PYTHONPATH=/app

USER appuser

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
