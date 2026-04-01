"""
MediSense AI — FastAPI Application Entry Point

This file:
  1. Creates the FastAPI app with metadata (feeds Swagger UI auto-docs)
  2. Configures CORS (which frontends can call the API)
  3. Adds security middleware (security headers on every response)
  4. Registers the API router
  5. Handles startup/shutdown lifecycle events
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine
from app.api.v1.router import api_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events.

    On startup: verify DB connection (fail fast if DB is unreachable)
    On shutdown: dispose DB connection pool gracefully
    """
    # Startup
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("✓ PostgreSQL connection verified")
    except Exception as e:
        print(f"✗ PostgreSQL connection failed: {e}")
        raise

    yield  # app runs here

    # Shutdown
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
    docs_url=f"{settings.API_V1_PREFIX}/docs",       # Swagger UI (US-45)
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────
# Only allow explicitly listed origins.
# In development: add http://localhost:3000 (React dev server)
# In production: only the actual frontend domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── Security Headers Middleware ───────────────────────────
# Added to EVERY response — not per-endpoint.
# These headers prevent common web attacks.
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # Prevent clickjacking (embedding in iframes)
    response.headers["X-Frame-Options"] = "DENY"
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Force HTTPS for 1 year (only effective behind nginx with HTTPS)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Restrict what resources the page can load (prevents XSS data exfiltration)
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    # Don't send referrer header to external sites (privacy)
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


# ── Routes ────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# ── Global Exception Handler ──────────────────────────────
# Ensures error responses never leak stack traces in production
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if settings.APP_ENV == "development":
        # In dev, show the full error for debugging
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__}
        )
    # In production, never expose internal error details
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred"}
    )
