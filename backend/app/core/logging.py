"""
Structured JSON logging setup.

Every log record includes:
- timestamp (ISO-8601)
- level
- logger name
- message
- any extra fields passed as kwargs to the logger
- correlation_id (if set in context var)

Usage:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("video processed", extra={"video_id": 123, "duration_ms": 456})
"""

import logging
import sys
from contextvars import ContextVar
from typing import Any

from pythonjsonlogger import jsonlogger

from app.core.config import settings

# Context variable that Celery/FastAPI middleware sets per-request / per-task.
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


class _CorrelationIdFilter(logging.Filter):
    """Injects the current correlation_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.correlation_id = correlation_id_var.get("")
        return True


class _CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Adds a few extra fields to every JSON log record."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["app"] = settings.APP_NAME
        log_record["env"] = settings.APP_ENV
        if not log_record.get("level"):
            log_record["level"] = record.levelname
        if not log_record.get("logger"):
            log_record["logger"] = record.name
        # Promote correlation_id if present
        if record.correlation_id:  # type: ignore[attr-defined]
            log_record["correlation_id"] = record.correlation_id  # type: ignore[attr-defined]


def configure_logging() -> None:
    """
    Call once at application startup (in main.py / worker entrypoint).
    Replaces the root handler with a JSON handler on stdout.
    """
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _CustomJsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    handler.addFilter(_CorrelationIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Silence noisy third-party loggers in production
    if settings.is_production:
        for noisy in ("httpx", "httpcore", "urllib3", "celery.redirected"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger. Logging must already be configured."""
    return logging.getLogger(name)
