"""
MediSense AI — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
from pathlib import Path
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
import time

from app.core.config import get_settings
from app.db.session import engine
from app.api.v1.router import api_router
from app.api.v1.endpoints.metrics import http_requests_total, http_request_duration_seconds

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # PostgreSQL
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("✓ PostgreSQL connection verified")
    except Exception as e:
        print(f"✗ PostgreSQL connection failed: {e}")
        raise

    # Qdrant (non-blocking — may not be needed for all routes)
    try:
        from app.rag.vectorstore import ensure_collection, get_collection_info
        ensure_collection()
        info = get_collection_info()
        print(f"✓ Qdrant collection '{info['name']}' ready ({info['points_count']} points)")
    except Exception as e:
        print(f"⚠ Qdrant not available (RAG endpoints will fail): {e}")

    # LLM provider health check (non-blocking)
    try:
        from app.rag.llm import check_health
        provider = settings.LLM_PROVIDER.upper()
        llm_ok = await check_health()
        if llm_ok:
            model = settings.GROQ_MODEL if settings.LLM_PROVIDER == "groq" else settings.OLLAMA_MODEL
            print(f"✓ LLM provider [{provider}] ready — model: {model}")
        else:
            print(f"⚠ LLM provider [{provider}] not reachable (chat will fail)")
    except Exception as e:
        print(f"⚠ LLM provider check failed: {e}")

    # Prometheus metric seeding — initialise label combinations to zero so
    # Grafana panels render "0" rather than "No data" out of the box.
    try:
        from app.api.v1.endpoints.metrics import seed_metrics, model_age_seconds
        seed_metrics()
        from pathlib import Path
        import os, time as _t
        lstm_path = Path(settings.LSTM_MODEL_PATH)
        if lstm_path.exists():
            age = _t.time() - os.path.getmtime(lstm_path)
            model_age_seconds.labels(model="lstm_anomaly").set(age)
        print("✓ Prometheus metrics seeded")
    except Exception as e:
        print(f"⚠ Metric seeding failed: {e}")

    # Kafka IoT consumer — persists iot-vitals messages into biometric_reading
    try:
        from app.services.kafka_consumer import start_kafka_consumer, stop_kafka_consumer
        await start_kafka_consumer()
        print("✓ IoT Kafka consumer task scheduled")
    except Exception as e:
        print(f"⚠ IoT Kafka consumer failed to start: {e}")
        stop_kafka_consumer = None  # type: ignore[assignment]

    yield

    if stop_kafka_consumer is not None:
        try:
            await stop_kafka_consumer()
        except Exception as e:
            print(f"⚠ IoT Kafka consumer shutdown error: {e}")

    await engine.dispose()
    print("✓ Database connections closed")


app = FastAPI(
    title="MediSense AI",
    description=(
        "Cognitive HealthTech Platform — "
        "Autonomous LLM Agents · Secure RAG · Predictive IoT Analytics\n\n"
        "**PFE 2025-2026** | Abderrahim Boussyf | EMSI Marrakech | n.synergy"
    ),
    version="1.0.0",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=None,   # disabled — custom route below serves local assets
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

# ── Static files (Swagger UI assets) ─────────────────────
# Path resolves relative to this file → works both inside Docker and locally
_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
else:
    logger.warning("Static directory not found at %s; skipping /static mount", _STATIC_DIR)

# ── CORS ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Prometheus Middleware ─────────────────────────────────
@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    start_time = time.time()
    
    # Skip metrics endpoint to avoid noise
    if request.url.path == f"{settings.API_V1_PREFIX}/metrics":
        return await call_next(request)

    response = await call_next(request)
    
    duration = time.time() - start_time
    
    # We use request.scope.get("route") to get the generic path (e.g. /patients/{uuid})
    # instead of the specific path (e.g. /patients/123) to avoid label cardinality explosion.
    route = request.scope.get("route")
    path = route.path if route else request.url.path
    
    http_requests_total.labels(
        method=request.method,
        endpoint=path,
        status_code=response.status_code
    ).inc()
    
    http_request_duration_seconds.labels(
        method=request.method,
        endpoint=path
    ).observe(duration)
    
    return response


# ── Global exception handler — ensures CORS headers on 500 ───────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    origin = request.headers.get("origin", "")
    headers: dict[str, str] = {}
    if origin in settings.CORS_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
        headers=headers,
    )


# ── Security Headers ──────────────────────────────────────
_DOCS_PREFIX = settings.API_V1_PREFIX + "/docs"

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Swagger UI needs 'unsafe-inline' for its inline scripts/styles.
    # Scope the relaxed CSP only to /docs* and /static* — all API endpoints
    # keep the strict policy (no unsafe-inline).
    path = request.url.path
    if path.startswith(_DOCS_PREFIX) or path.startswith("/static"):
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:"
        )
    else:
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:"
        )
    response.headers["Content-Security-Policy"] = csp
    return response


# ── Custom Swagger UI (local assets — no CDN) ─────────────
@app.get(f"{settings.API_V1_PREFIX}/docs", include_in_schema=False)
async def custom_swagger_ui() -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        title="MediSense AI — Swagger UI",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
        oauth2_redirect_url=f"{settings.API_V1_PREFIX}/docs/oauth2-redirect",
    )


@app.get(f"{settings.API_V1_PREFIX}/docs/oauth2-redirect", include_in_schema=False)
async def swagger_oauth2_redirect() -> HTMLResponse:
    return get_swagger_ui_oauth2_redirect_html()


# ── Routes ────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


