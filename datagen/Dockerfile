# Single-stage image
FROM python:3.12-slim

# Environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DB_PATH="/data/app.db"

# System deps for healthcheck & debugging
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy source
COPY app/ /app/app

# Create data directory and make it writable by 'nobody'
RUN mkdir -p /data && chown -R nobody:nogroup /data /app

# Switch to nobody user
USER nobody:nogroup

EXPOSE 8000

# Healthcheck hits /healthz
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/healthz || exit 1

# Start the FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
