# Production image for DigitalOcean App Platform.
#
# Why a separate Dockerfile (not the main one)?
#   The main Dockerfile installs requirements.txt — the full training/MLOps
#   stack (~6GB with the CUDA torch wheel) — which OOM/disk-exhausts DO's build
#   node when it snapshots the image layer. This image installs only the slim
#   runtime set (requirements-prod.txt) plus the CPU-only torch wheel, keeping
#   the image small enough to build. The local Dockerfile + docker-compose are
#   left untouched.
FROM python:3.11-slim

WORKDIR /app

# Runtime system deps + build tools (gcc for langdetect, libpq for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps. CPU-only torch FIRST (from the PyTorch CPU index) so the
# ~4GB of nvidia-cu* CUDA wheels are never pulled — we only do CPU inference.
ARG PIP_REQUIREMENTS=requirements-prod.txt
ARG TORCH_VERSION=2.2.2
COPY requirements*.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir "torch==${TORCH_VERSION}" \
        --index-url https://download.pytorch.org/whl/cpu && \
    test -f "${PIP_REQUIREMENTS}" && pip install --no-cache-dir -r "${PIP_REQUIREMENTS}"

# Download Swagger UI assets locally (avoid CDN dependency at runtime)
ARG SWAGGER_UI_VERSION=5.11.0
RUN mkdir -p /app/static && \
    curl -fsSL "https://cdn.jsdelivr.net/npm/swagger-ui-dist@${SWAGGER_UI_VERSION}/swagger-ui.css" \
         -o /app/static/swagger-ui.css && \
    curl -fsSL "https://cdn.jsdelivr.net/npm/swagger-ui-dist@${SWAGGER_UI_VERSION}/swagger-ui-bundle.js" \
         -o /app/static/swagger-ui-bundle.js

# Copy application code
COPY . .

# Non-root user (security best practice)
RUN useradd -m -u 1000 medisense && chown -R medisense:medisense /app
USER medisense

# NOTE: the DO spec overrides this via run_command (init_db && uvicorn).
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--log-level", "info"]
