# ── Build stage ──────────────────────────────────────────
# Why multi-stage? Production image won't contain build tools or cache
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies (needed for some Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install only runtime dependencies (not build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built wheels from builder stage
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache /wheels/*

# Download Swagger UI assets locally (avoid CDN dependency)
RUN mkdir -p /app/static && \
    curl -sL https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css \
         -o /app/static/swagger-ui.css && \
    curl -sL https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js \
         -o /app/static/swagger-ui-bundle.js

# Copy application code
COPY . .

# Non-root user (security best practice — never run as root in containers)
RUN useradd -m -u 1000 medisense && chown -R medisense:medisense /app
USER medisense

# Uvicorn with reload for development
# In production: remove --reload and increase --workers
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload", \
     "--log-level", "info"]
