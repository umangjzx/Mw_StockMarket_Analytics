"""
Discovery tasks — channel polling and video metadata sync.
Implemented in Phase 1a.
"""

import asyncio

from app.core.celery_app import celery_app
from app.core.logging import get_logger
from app.db.session import create_worker_session
from app.providers.video_platforms.youtube_provider import YouTubeProvider
from app.services.channel_discovery_service import ChannelDiscoveryService
from app.services.quota_tracker import QuotaTracker
from app.repositories.channel_repository import ChannelRepository

logger = get_logger(__name__)


@celery_app.task(name="app.workers.tasks.discovery_tasks.poll_channel", bind=True)
def poll_channel(self, channel_id: int | None = None) -> dict:
    """
    Poll one channel (or all active channels if channel_id is None) for new videos.
    Phase 1a implementation.
    """
    return asyncio.run(_poll_channel_async(channel_id))


async def _poll_channel_async(channel_id: int | None) -> dict:
    async with create_worker_session() as session:
        channel_repo = ChannelRepository(session)

        if channel_id:
            channel = await channel_repo.get_by_id(channel_id)
            if not channel:
                logger.error("Channel not found", extra={"channel_id": channel_id})
                return {"status": "error", "message": "Channel not found"}
            channels = [channel]
        else:
            channels = await channel_repo.list_active()

        if not channels:
            logger.info("No active channels to poll")
            return {"status": "ok", "polled": 0}

        provider = YouTubeProvider()
        quota = QuotaTracker()
        service = ChannelDiscoveryService(session, provider, quota)

        results = []
        for ch in channels:
            try:
                summary = await service.poll_channel(ch)
                await session.commit()
                results.append(summary)
            except Exception as exc:
                await session.rollback()
                logger.exception("Poll failed", extra={"channel_id": ch.id, "error": str(exc)})
                await channel_repo.mark_polled(ch.id, success=False)
                await session.commit()
                results.append({"channel_id": ch.id, "error": str(exc)})

        return {"status": "ok", "polled": len(channels), "results": results}


@celery_app.task(name="app.workers.tasks.discovery_tasks.sync_video_metadata", bind=True)
def sync_video_metadata(self, video_id: int) -> dict:
    """Sync full metadata for a single video. Phase 1a: not yet needed, reserved for manual refresh."""
    logger.info("sync_video_metadata stub", extra={"video_id": video_id})
    return {"status": "not_implemented", "video_id": video_id}


@celery_app.task(name="app.workers.tasks.discovery_tasks.refresh_video_stats", bind=True)
def refresh_video_stats(self) -> dict:
    """Re-fetch view/like/comment counts for recently published videos. Phase 1a implementation."""
    return asyncio.run(_refresh_stats_async())


async def _refresh_stats_async() -> dict:
    async with create_worker_session() as session:
        channel_repo = ChannelRepository(session)
        channels = await channel_repo.list_active()

        if not channels:
            return {"status": "ok", "channels": 0, "videos": 0}

        provider = YouTubeProvider()
        quota = QuotaTracker()
        service = ChannelDiscoveryService(session, provider, quota)

        total_videos = 0
        for ch in channels:
            try:
                count = await service.refresh_video_stats(ch)
                await session.commit()
                total_videos += count
                logger.info("Refreshed stats for channel", extra={"channel_id": ch.id, "videos": count})
            except Exception as exc:
                await session.rollback()
                logger.exception("Stat refresh failed", extra={"channel_id": ch.id, "error": str(exc)})

        return {"status": "ok", "channels": len(channels), "videos": total_videos}


@celery_app.task(name="app.workers.tasks.discovery_tasks.process_single_video_url", bind=True)
def process_single_video_url(self, url: str) -> dict:
    """
    Process a single YouTube video by URL — NO API KEY NEEDED.
    Uses yt-dlp to fetch metadata, creates video+channel records, triggers full pipeline.
    """
    return asyncio.run(_process_single_url_async(url))


async def _process_single_url_async(url: str) -> dict:
    """Fetch metadata via yt-dlp, persist to DB, enqueue pipeline."""
    from app.repositories.video_repository import VideoRepository
    from app.workers.pipeline import enqueue_pipeline_from
    from app.providers.video_platforms.ytdlp_provider import YtdlpProvider

    async with create_worker_session() as session:
        video_repo = VideoRepository(session)
        channel_repo = ChannelRepository(session)
        ytdlp = YtdlpProvider()

        try:
            # Check if already in DB first (skip yt-dlp call if so)
            import re
            patterns = [
                r'(?:v=|/)([0-9A-Za-z_-]{11}).*',
                r'(?:embed/)([0-9A-Za-z_-]{11})',
                r'^([0-9A-Za-z_-]{11})$',
            ]
            external_video_id = None
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    external_video_id = match.group(1)
                    break

            if external_video_id:
                existing = await video_repo.find_by_external_id(external_video_id)
                if existing:
                    logger.info("Video already exists, re-triggering pipeline",
                                extra={"video_id": existing.id})
                    task_id = enqueue_pipeline_from(existing.id, "DISCOVERED")
                    return {
                        "status": "reprocessing",
                        "video_id": existing.id,
                        "title": existing.title,
                        "external_video_id": external_video_id,
                        "task_id": task_id,
                    }

            # Fetch metadata via yt-dlp (no API key needed)
            logger.info("Fetching video metadata via yt-dlp", extra={"url": url})
            video_info, channel_info = await ytdlp.get_video_info(url)

            # Upsert channel
            channel, ch_created = await channel_repo.upsert(
                platform="youtube",
                external_channel_id=channel_info.external_channel_id,
                defaults={
                    "display_name": channel_info.display_name,
                    "handle": channel_info.handle,
                    "description": channel_info.description,
                    "thumbnail_url": channel_info.thumbnail_url,
                    "subscriber_count": channel_info.subscriber_count,
                    "is_active": True,
                },
            )
            await session.commit()
            logger.info(
                f"Channel {'created' if ch_created else 'found'}",
                extra={"channel_id": channel.id, "display_name": channel.display_name}
            )

            # Upsert video
            video, vid_created = await video_repo.upsert_discovered(
                channel_id=channel.id,
                external_video_id=video_info.external_video_id,
                defaults={
                    "video_url": video_info.video_url,
                    "title": video_info.title,
                    "description": video_info.description,
                    "thumbnail_url": video_info.thumbnail_url,
                    "published_at": video_info.published_at,
                    "duration_seconds": video_info.duration_seconds,
                    "language": video_info.language,
                    "tags": video_info.tags or [],
                    "category": video_info.category,
                    "content_type": video_info.content_type,
                    "view_count": video_info.view_count,
                    "like_count": video_info.like_count,
                    "comment_count": video_info.comment_count,
                },
            )
            await session.commit()

            logger.info(
                f"Video {'created' if vid_created else 'updated'}: {video.title}",
                extra={"video_id": video.id}
            )

            # Enqueue full pipeline
            task_id = enqueue_pipeline_from(video.id, "DISCOVERED")

            return {
                "status": "created" if vid_created else "updated",
                "video_id": video.id,
                "external_video_id": video_info.external_video_id,
                "title": video_info.title,
                "channel": channel.display_name,
                "duration_seconds": video_info.duration_seconds,
                "task_id": task_id,
            }

        except Exception as exc:
            await session.rollback()
            logger.exception("Failed to process video URL", extra={"url": url, "error": str(exc)})
            raise
