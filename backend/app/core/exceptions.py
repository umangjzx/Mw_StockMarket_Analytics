"""
Domain exceptions and their HTTP error mapping.

Raise domain exceptions in services/repositories and let the FastAPI exception
handlers in main.py translate them into proper HTTP responses. Never import HTTPException
in services or repositories.
"""

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


# ── Domain Exceptions ─────────────────────────────────────────────────────────


class MWBaseError(Exception):
    """Root exception for all domain errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or message


class NotFoundError(MWBaseError):
    """Resource does not exist."""

    status_code = 404
    error_code = "NOT_FOUND"


class AlreadyExistsError(MWBaseError):
    """Resource already exists (uniqueness violation)."""

    status_code = 409
    error_code = "ALREADY_EXISTS"


class ValidationError(MWBaseError):
    """Input failed domain-level validation (not Pydantic schema validation)."""

    status_code = 422
    error_code = "VALIDATION_ERROR"


class AuthenticationError(MWBaseError):
    """Missing or invalid credentials."""

    status_code = 401
    error_code = "AUTHENTICATION_ERROR"


class AuthorizationError(MWBaseError):
    """Authenticated user lacks the required role/permission."""

    status_code = 403
    error_code = "AUTHORIZATION_ERROR"


class ExternalServiceError(MWBaseError):
    """An upstream service (YouTube, OpenAI, Whisper) returned an unexpected error."""

    status_code = 502
    error_code = "EXTERNAL_SERVICE_ERROR"


class QuotaExceededError(MWBaseError):
    """YouTube Data API or OpenAI quota / rate-limit reached."""

    status_code = 429
    error_code = "QUOTA_EXCEEDED"


class PipelineError(MWBaseError):
    """Video processing pipeline error."""

    status_code = 500
    error_code = "PIPELINE_ERROR"


class TranscriptionError(MWBaseError):
    """Transcript could not be obtained via any available provider."""

    status_code = 422
    error_code = "TRANSCRIPTION_ERROR"


# ── Exception Handlers ────────────────────────────────────────────────────────


async def domain_exception_handler(request: Request, exc: MWBaseError) -> JSONResponse:
    """Maps any MWBaseError subclass to a structured JSON HTTP response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "detail": exc.detail,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Formats FastAPI HTTPException as consistent JSON (same shape as domain errors)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": exc.detail,
            "detail": exc.detail,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unexpected exceptions — returns 500 without leaking internals."""
    import logging

    logging.getLogger(__name__).exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Please try again later.",
            "detail": None,
        },
    )
