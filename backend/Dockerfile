FROM python:3.11-slim

WORKDIR /app

# Runtime system deps + build tools (gcc needed for langdetect, psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Layer is cached by Docker as long as requirements*.txt doesn't change
ARG PIP_REQUIREMENTS=requirements.txt
COPY requirements*.txt ./
RUN pip install --upgrade pip && \
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

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload", \
     "--log-level", "info"]
