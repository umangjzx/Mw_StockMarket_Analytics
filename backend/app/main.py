"""
FastAPI application factory — the entrypoint for the API server.

Run via:
    uvicorn app.main:app --reload

or in production:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import (
    MWBaseError,
    domain_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
)
from app.core.logging import configure_logging, correlation_id_var, get_logger
from fastapi import HTTPException
import uuid

# ── Configure logging on import ───────────────────────────────────────────────

configure_logging()
logger = get_logger(__name__)


# ── Application factory ───────────────────────────────────────────────────────


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="AI Stock Market Video Intelligence Platform — Backend API",
        version="0.1.0",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
    )

    # ── Middleware ─────────────────────────────────────────────────────────────

    # CORS — open in development, restrictive in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Inject a unique correlation_id per request for log tracing."""
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        correlation_id_var.set(correlation_id)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response

    # ── Exception handlers ─────────────────────────────────────────────────────

    app.add_exception_handler(MWBaseError, domain_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ── Router mounting ────────────────────────────────────────────────────────

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "healthy", "environment": settings.APP_ENV}

    # Phase 1a: wire up /api/v1
    from app.api.v1.router import api_router
    app.include_router(api_router, prefix="/api/v1")

    # ── Startup / Shutdown events ──────────────────────────────────────────────

    @app.on_event("startup")
    async def startup() -> None:
        logger.info("Application startup", extra={"env": settings.APP_ENV})
        # Sentry init (if DSN is configured)
        if settings.SENTRY_DSN:
            import sentry_sdk
            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                environment=settings.APP_ENV,
                traces_sample_rate=0.1 if settings.is_production else 1.0,
            )

    @app.on_event("shutdown")
    async def shutdown() -> None:
        logger.info("Application shutdown")

    return app


# ── Module-level app instance ─────────────────────────────────────────────────

app = create_app()
