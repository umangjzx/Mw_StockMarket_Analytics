"""
Channel discovery service — orchestrates polling logic.

This service is the single place that knows how to:
1. Add a new channel (resolve handle → channel info → persist)
2. Poll a channel for new videos (diff against known IDs → insert new → enqueue pipeline)
3. Refresh stats for recently published videos
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AlreadyExistsError, NotFoundError
from app.core.logging import get_logger
from app.models.channel import Channel
from app.models.video import Video
from app.providers.video_platforms.base import ChannelInfo, VideoInfo, VideoPlatformProvider
from app.repositories.channel_repository import ChannelRepository
from app.repositories.video_repository import VideoRepository
from app.services.quota_tracker import QuotaTracker

logger = get_logger(__name__)


class ChannelDiscoveryService:
    """Orchestrates channel + video discovery."""

    def __init__(
        self,
        session: AsyncSession,
        provider: VideoPlatformProvider,
        quota_tracker: QuotaTracker,
    ) -> None:
        self._session = session
        self._provider = provider
        self._quota = quota_tracker
        self._channels = ChannelRepository(session)
        self._videos = VideoRepository(session)

    # ── Adding channels ───────────────────────────────────────────────────────

    async def add_channel(
        self,
        channel_id_or_handle: str,
        platform: str = "youtube",
        polling_interval_seconds: int = 900,
        include_shorts: bool = False,
    ) -> Channel:
        """
        Resolve a channel handle/ID, fetch metadata, and persist.
        Raises AlreadyExistsError if already configured.
        """
        # Quota cost: 1 unit for channels.list
        self._quota.check_and_reserve(1)

        channel_info: ChannelInfo = await self._provider.get_channel_info(channel_id_or_handle)
        self._quota.record_usage(1)

        # Check for duplicates
        existing = await self._channels.get_by_external_id(platform, channel_info.external_channel_id)
        if existing:
            raise AlreadyExistsError(
                f"Channel already exists: {channel_info.display_name}",
                detail=f"external_channel_id={channel_info.external_channel_id}",
            )

        channel, _ = await self._channels.upsert(
            platform=platform,
            external_channel_id=channel_info.external_channel_id,
            defaults={
                "handle": channel_info.handle,
                "display_name": channel_info.display_name,
                "description": channel_info.description,
                "thumbnail_url": channel_info.thumbnail_url,
                "country": channel_info.country,
                "subscriber_count": channel_info.subscriber_count,
                "polling_interval_seconds": polling_interval_seconds,
                "include_shorts": include_shorts,
                "is_active": True,
            },
        )
        logger.info(
            "Channel added",
            extra={"channel_id": channel.id, "name": channel.display_name},
        )
        return channel

    # ── Polling ───────────────────────────────────────────────────────────────

    async def poll_channel(self, channel: Channel) -> dict:
        """
        Discover new videos on a channel.
        Returns summary: {new: int, skipped: int, shorts_skipped: int}
        """
        logger.info("Polling channel", extra={"channel_id": channel.id, "name": channel.display_name})

        # Build ChannelInfo from persisted channel data
        channel_info = ChannelInfo(
            external_channel_id=channel.external_channel_id,
            display_name=channel.display_name,
            platform=channel.platform,
            handle=channel.handle,
            # We need the uploads playlist ID — fetch it if we don't have it
            uploads_playlist_id=self._derive_uploads_playlist_id(channel),
        )

        # If we don't have a playlist ID, re-fetch channel info (1 quota unit)
        if not channel_info.uploads_playlist_id:
            self._quota.check_and_reserve(1)
            fresh_info = await self._provider.get_channel_info(channel.external_channel_id)
            self._quota.record_usage(1)
            channel_info.uploads_playlist_id = fresh_info.uploads_playlist_id

        # Quota cost: 1 unit per page of playlistItems.list + 1 unit per batch of videos.list
        self._quota.check_and_reserve(2)  # conservative minimum for one page

        video_list: list[VideoInfo] = await self._provider.list_new_videos(
            channel=channel_info,
            since=channel.last_successful_poll_at,
            max_results=50,
        )
        # Approximate quota used: 1 for playlistItems.list + 1 for videos.list batch
        self._quota.record_usage(2)

        # Get already-known IDs to compute diff
        known_ids = await self._videos.get_known_ids(channel.id)

        new_count = 0
        skipped_count = 0
        shorts_skipped = 0

        for video_info in video_list:
            if video_info.external_video_id in known_ids:
                skipped_count += 1
                continue

            # Skip shorts if channel is configured not to include them
            if video_info.is_short and not channel.include_shorts:
                shorts_skipped += 1
                continue

            video, created = await self._videos.upsert_discovered(
                channel_id=channel.id,
                external_video_id=video_info.external_video_id,
                defaults=self._video_info_to_dict(video_info),
            )

            if created:
                new_count += 1
                logger.info(
                    "New video discovered",
                    extra={
                        "video_id": video.id,
                        "external_id": video_info.external_video_id,
                        "title": video_info.title[:80],
                        "channel_id": channel.id,
                    },
                )
                # Enqueue transcript fetch immediately
                from app.workers.tasks.transcript_tasks import fetch_captions
                fetch_captions.apply_async(
                    args=[video.id],
                    queue="transcription",
                )

        # Update poll timestamps
        await self._channels.mark_polled(channel.id, success=True)

        summary = {
            "channel_id": channel.id,
            "new": new_count,
            "already_known": skipped_count,
            "shorts_skipped": shorts_skipped,
        }
        logger.info("Poll complete", extra=summary)
        return summary

    async def refresh_video_stats(self, channel: Channel) -> int:
        """
        Re-fetch view/like/comment counts for recently published videos on this channel.
        Writes a stat snapshot + updates denormalized counts.
        Returns number of videos refreshed.
        """
        recent = await self._videos.list_recently_published(days=14)
        channel_videos = [v for v in recent if v.channel_id == channel.id]

        if not channel_videos:
            return 0

        self._quota.check_and_reserve(1)
        stats = await self._provider.get_video_stats(
            [v.external_video_id for v in channel_videos]
        )
        self._quota.record_usage(1)

        for video in channel_videos:
            s = stats.get(video.external_video_id, {})
            if not s:
                continue
            await self._videos.update_stats(
                video.id,
                view_count=s.get("view_count"),
                like_count=s.get("like_count"),
                comment_count=s.get("comment_count"),
            )
            await self._videos.add_stat_snapshot(
                video.id,
                view_count=s.get("view_count"),
                like_count=s.get("like_count"),
                comment_count=s.get("comment_count"),
            )

        return len(channel_videos)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _derive_uploads_playlist_id(channel: Channel) -> str | None:
        """
        For YouTube: uploads playlist = 'UU' + channel_id[2:]
        This avoids a channels.list call for channels we've already stored.
        """
        if channel.platform != "youtube":
            return None
        ext_id = channel.external_channel_id
        if ext_id.startswith("UC") and len(ext_id) > 2:
            return "UU" + ext_id[2:]
        return None

    @staticmethod
    def _video_info_to_dict(info: VideoInfo) -> dict:
        return {
            "video_url": info.video_url,
            "title": info.title,
            "description": info.description,
            "thumbnail_url": info.thumbnail_url,
            "published_at": info.published_at,
            "duration_seconds": info.duration_seconds,
            "language": info.language,
            "tags": info.tags or [],
            "category": info.category,
            "content_type": info.content_type,
            "live_status": info.live_status,
            "view_count": info.view_count,
            "like_count": info.like_count,
            "comment_count": info.comment_count,
        }
