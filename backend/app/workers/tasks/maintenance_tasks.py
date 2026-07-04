"""Maintenance tasks — retry sweeps, media cache cleanup, quota resets."""

import asyncio
import os
import time

import redis

from app.core.celery_app import celery_app
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.retry_failed_pipelines",
    bind=True,
)
def retry_failed_pipelines(self) -> dict:
    """Re-queue FAILED videos where retry_count < max and next_retry_at <= now."""
    return asyncio.run(_retry_failed_async())


async def _retry_failed_async() -> dict:
    from app.db.session import create_worker_session
    from app.repositories.video_repository import VideoRepository
    from app.workers.pipeline import enqueue_pipeline_from

    async with create_worker_session() as session:
        repo = VideoRepository(session)
        retryable = await repo.list_retryable(max_retries=settings.MAX_PIPELINE_RETRIES)

        if not retryable:
            logger.info("No retryable failed pipelines")
            return {"status": "ok", "enqueued": 0}

        enqueued = 0
        for video in retryable:
            try:
                # Compute exponential backoff for next retry
                from datetime import UTC, datetime, timedelta
                backoff = min(
                    60 * (2 ** video.pipeline_retry_count),
                    settings.PIPELINE_RETRY_BACKOFF_MAX,
                )
                next_retry = datetime.now(UTC) + timedelta(seconds=backoff)

                await repo.set_pipeline_status(
                    video.id,
                    "TRANSCRIPT_PENDING",
                    failure_reason=None,
                    next_retry_at=next_retry,
                )
                enqueue_pipeline_from(video.id, "TRANSCRIPT_PENDING")
                enqueued += 1
                logger.info(
                    "Re-enqueued failed video",
                    extra={"video_id": video.id, "retry_count": video.pipeline_retry_count},
                )
            except Exception as exc:
                logger.exception(
                    "Failed to re-enqueue video",
                    extra={"video_id": video.id, "error": str(exc)},
                )

        await session.commit()

    return {"status": "ok", "enqueued": enqueued}


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.cleanup_media_cache",
    bind=True,
)
def cleanup_media_cache(self) -> dict:
    """Delete cached audio/video files older than the retention window."""
    retention_seconds = settings.MEDIA_RETENTION_HOURS * 3600
    cache_dir = settings.MEDIA_CACHE_DIR
    deleted = 0

    if not os.path.isdir(cache_dir):
        logger.info("Media cache dir not found, skipping", extra={"dir": cache_dir})
        return {"status": "skipped", "reason": "dir_not_found"}

    cutoff = time.time() - retention_seconds
    for fname in os.listdir(cache_dir):
        fpath = os.path.join(cache_dir, fname)
        try:
            if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
                deleted += 1
        except OSError as exc:
            logger.warning("Failed to delete file", extra={"path": fpath, "error": str(exc)})

    logger.info("Media cache cleanup complete", extra={"deleted": deleted})
    return {"status": "ok", "deleted": deleted}


@celery_app.task(
    name="app.workers.tasks.maintenance_tasks.reset_quota_counters",
    bind=True,
)
def reset_quota_counters(self) -> dict:
    """Reset YouTube API daily quota counter in Redis at midnight UTC."""
    from app.services.quota_tracker import QuotaTracker
    QuotaTracker().reset()
    return {"status": "ok"}
