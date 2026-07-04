"""
Quota tracking service for YouTube Data API.

Tracks daily quota consumption in Redis and throttles before hitting the ceiling.
Reset daily at midnight UTC via a maintenance task.
"""

import redis
from app.core.config import settings
from app.core.exceptions import QuotaExceededError
from app.core.logging import get_logger

logger = get_logger(__name__)


class QuotaTracker:
    """Tracks YouTube API quota usage (Redis-backed)."""

    QUOTA_KEY = "quota:youtube:daily_units"

    def __init__(self) -> None:
        self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    def record_usage(self, units: int) -> int:
        """
        Increment quota usage by `units` and return new total.
        Call this AFTER a successful API call.
        """
        new_total = self._redis.incr(self.QUOTA_KEY, units)
        logger.info("YouTube quota usage", extra={"units": units, "total": new_total})
        return new_total

    def check_and_reserve(self, units: int) -> None:
        """
        Check if adding `units` would exceed the limit.
        Call this BEFORE making an API call.
        Raises QuotaExceededError if insufficient quota remains.
        """
        current = self.get_current_usage()
        if current + units > settings.YOUTUBE_DAILY_QUOTA_LIMIT:
            raise QuotaExceededError(
                f"YouTube quota exhausted: {current}/{settings.YOUTUBE_DAILY_QUOTA_LIMIT} used, need {units} more"
            )

    def get_current_usage(self) -> int:
        """Return current quota usage for the day."""
        val = self._redis.get(self.QUOTA_KEY)
        return int(val) if val else 0

    def reset(self) -> None:
        """Reset quota counter (called by maintenance task at midnight UTC)."""
        self._redis.set(self.QUOTA_KEY, 0)
        logger.info("YouTube quota counter reset")
