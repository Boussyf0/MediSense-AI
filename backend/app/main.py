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

from app.core.config import get_settings
from app.db.session import engine
from app.api.v1.router import api_router

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

    # Ollama (non-blocking — check if Mistral model is loaded)
    try:
        from app.rag.llm import check_health
        ollama_ok = await check_health()
        if ollama_ok:
            print("✓ Ollama + Mistral 7B ready")
        else:
            print("⚠ Ollama reachable but Mistral model not loaded (run: ollama pull mistral:7b)")
    except Exception as e:
        print(f"⚠ Ollama not available (chat will fail): {e}")

    yield

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


# ── Global Exception Handler ──────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if settings.APP_ENV == "development":
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__}
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred"}
    )
