"""
Abstract interface for video platform providers.

All platform adapters (YouTube, podcast RSS, Twitter/X) implement this interface.
Business logic in services/ and workers/ depends only on this — never on
a concrete SDK.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ChannelInfo:
    """Normalised channel metadata returned by any platform provider."""
    external_channel_id: str
    display_name: str
    platform: str = "youtube"
    handle: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    country: str | None = None
    subscriber_count: int | None = None
    uploads_playlist_id: str | None = None  # YouTube-specific, ignored by other providers


@dataclass
class VideoInfo:
    """Normalised video metadata returned by any platform provider."""
    external_video_id: str
    title: str
    video_url: str
    published_at: datetime
    platform: str = "youtube"
    description: str | None = None
    thumbnail_url: str | None = None
    duration_seconds: int | None = None
    language: str | None = None
    tags: list[str] = field(default_factory=list)
    category: str | None = None
    content_type: str = "video"          # video | short | live | scheduled | podcast
    live_status: str | None = None       # none | upcoming | live | completed
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None
    is_short: bool = False


class VideoPlatformProvider(ABC):
    """Port that all video platform adapters must implement."""

    @abstractmethod
    async def get_channel_info(self, channel_id_or_handle: str) -> ChannelInfo:
        """
        Fetch channel metadata by channel ID or handle (e.g. '@CNBC').
        Raises ExternalServiceError on API failures, QuotaExceededError on quota exhaustion.
        """

    @abstractmethod
    async def list_new_videos(
        self,
        channel: ChannelInfo,
        since: datetime | None = None,
        max_results: int = 50,
    ) -> list[VideoInfo]:
        """
        Return videos published after `since` (or all recent if None).
        Results are ordered newest-first. Implementations should handle pagination
        internally and stop once `since` is crossed or `max_results` is reached.
        """

    @abstractmethod
    async def get_video_stats(self, external_video_ids: list[str]) -> dict[str, dict]:
        """
        Batch-fetch current view/like/comment counts.
        Returns {external_video_id: {view_count, like_count, comment_count}}.
        """
