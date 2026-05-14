# Multi-stage Dockerfile for FastAPI application

# Base stage with common dependencies
FROM python:3.12-slim AS base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_CACHE_DIR=/tmp/uv-cache

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Create app directory
WORKDIR /app

# Copy shared package to /shared so uv resolves the path from pyproject.toml
# (uv.lock records it as `editable = "../shared"`, relative to /app)
COPY shared /shared

# Copy dependency files
COPY pyproject.toml uv.lock ./

# COPY google-cloud-service-account-key.json ./google-cloud-service-account-key.json

# Development stage
FROM base AS development

# Install all dependencies (including dev dependencies)
RUN uv sync --frozen

# Copy application code
COPY src/ ./src/
COPY tests/ ./tests/
COPY run_dev.py ./

# Expose port
EXPOSE 8000

# Run with reload for development
CMD ["uv", "run", "uvicorn", "src.kene_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production stage
FROM base AS production

# Install only production dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY src/ ./src/

# Create non-root user for security and set up permissions
RUN groupadd -r appuser && useradd -r -g appuser appuser && \
    mkdir -p /tmp/uv-cache && \
    chown -R appuser:appuser /app /shared /tmp/uv-cache
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uv", "run", "uvicorn", "src.kene_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
