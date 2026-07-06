"""
Quota tracking service — daily request counters per external service
(YouTube, Groq, Ollama), Redis-backed. YouTube is quota-limited and throttled
before hitting its ceiling; Groq/Ollama have no hard limit enforced here
(Groq's free tier is generous, Ollama is self-hosted) but are counted the
same way so the admin dashboard can show real usage instead of nothing.
Reset daily at midnight UTC via a maintenance task.
"""

import redis
from app.core.config import settings
from app.core.exceptions import QuotaExceededError
from app.core.logging import get_logger

logger = get_logger(__name__)

KNOWN_SERVICES = ("youtube", "groq", "ollama")


class QuotaTracker:
    """Tracks per-service API usage (Redis-backed)."""

    def __init__(self) -> None:
        self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    def _key(self, service: str) -> str:
        return f"quota:{service}:daily_units"

    def record_usage(self, units: int = 1, service: str = "youtube") -> int:
        """
        Increment quota usage by `units` and return new total.
        Call this AFTER a successful API call.
        """
        new_total = self._redis.incr(self._key(service), units)
        logger.info(f"{service} quota usage", extra={"service": service, "units": units, "total": new_total})
        return new_total

    def check_and_reserve(self, units: int, service: str = "youtube") -> None:
        """
        Check if adding `units` would exceed the limit.
        Call this BEFORE making an API call.
        Raises QuotaExceededError if insufficient quota remains.
        Only YouTube has an enforced daily limit today.
        """
        if service != "youtube":
            return
        current = self.get_current_usage(service)
        if current + units > settings.YOUTUBE_DAILY_QUOTA_LIMIT:
            raise QuotaExceededError(
                f"YouTube quota exhausted: {current}/{settings.YOUTUBE_DAILY_QUOTA_LIMIT} used, need {units} more"
            )

    def get_current_usage(self, service: str = "youtube") -> int:
        """Return current usage for the day for the given service."""
        val = self._redis.get(self._key(service))
        return int(val) if val else 0

    def reset(self, service: str | None = None) -> None:
        """Reset one service's counter, or all known services if none given.
        Called by the daily maintenance task at midnight UTC."""
        services = (service,) if service else KNOWN_SERVICES
        for s in services:
            self._redis.set(self._key(s), 0)
        logger.info("Quota counters reset", extra={"services": list(services)})
