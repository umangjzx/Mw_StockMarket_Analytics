"""
YouTube Data API v3 adapter.

Quota costs per call (against 10,000 daily units):
- channels.list: 1 unit
- search.list: 100 units (expensive!)
- playlistItems.list: 1 unit (preferred for channel video discovery)
- videos.list: 1 unit

Strategy: fetch uploads playlist from channel, iterate via playlistItems.list.
"""

import isodate
from datetime import UTC, datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings
from app.core.exceptions import ExternalServiceError, NotFoundError, QuotaExceededError
from app.core.logging import get_logger
from app.providers.video_platforms.base import ChannelInfo, VideoInfo, VideoPlatformProvider

logger = get_logger(__name__)


class YouTubeProvider(VideoPlatformProvider):
    """YouTube Data API v3 client."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.YOUTUBE_API_KEY
        if not self.api_key:
            raise ValueError("YOUTUBE_API_KEY not configured")
        self._youtube = build("youtube", "v3", developerKey=self.api_key)

    async def get_channel_info(self, channel_id_or_handle: str) -> ChannelInfo:
        """Fetch channel metadata. Accepts channel ID (UC...) or handle (@CNBC)."""
        try:
            # Normalize handle format
            if channel_id_or_handle.startswith("@"):
                search_by = "forHandle"
                search_val = channel_id_or_handle
            elif channel_id_or_handle.startswith("UC"):
                search_by = "id"
                search_val = channel_id_or_handle
            else:
                # Assume bare handle like 'CNBC'
                search_by = "forHandle"
                search_val = f"@{channel_id_or_handle}"

            request = self._youtube.channels().list(
                part="snippet,contentDetails,statistics",
                **{search_by: search_val},
                maxResults=1,
            )
            response = request.execute()

            if not response.get("items"):
                raise NotFoundError(f"Channel not found: {channel_id_or_handle}")

            item = response["items"][0]
            snippet = item["snippet"]
            stats = item.get("statistics", {})
            content_details = item.get("contentDetails", {})

            return ChannelInfo(
                external_channel_id=item["id"],
                display_name=snippet["title"],
                platform="youtube",
                handle=snippet.get("customUrl"),  # May be None
                description=snippet.get("description"),
                thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url"),
                country=snippet.get("country"),
                subscriber_count=int(stats.get("subscriberCount", 0)) if stats.get("subscriberCount") else None,
                uploads_playlist_id=content_details.get("relatedPlaylists", {}).get("uploads"),
            )

        except HttpError as exc:
            if exc.resp.status == 403 and "quotaExceeded" in str(exc):
                raise QuotaExceededError("YouTube Data API quota exceeded") from exc
            raise ExternalServiceError(f"YouTube API error: {exc}") from exc

    async def list_new_videos(
        self,
        channel: ChannelInfo,
        since: datetime | None = None,
        max_results: int = 50,
    ) -> list[VideoInfo]:
        """
        Fetch videos from channel's uploads playlist using playlistItems.list.
        Stops once we encounter a video older than `since` or hit `max_results`.
        """
        if not channel.uploads_playlist_id:
            logger.warning("Channel has no uploads playlist", extra={"channel": channel.external_channel_id})
            return []

        videos: list[VideoInfo] = []
        page_token: str | None = None

        try:
            while len(videos) < max_results:
                request = self._youtube.playlistItems().list(
                    part="snippet,contentDetails",
                    playlistId=channel.uploads_playlist_id,
                    maxResults=min(50, max_results - len(videos)),
                    pageToken=page_token,
                )
                response = request.execute()

                for item in response.get("items", []):
                    snippet = item["snippet"]
                    video_id = snippet["resourceId"]["videoId"]
                    published_str = snippet["publishedAt"]
                    published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))

                    # Stop if we've gone past the `since` cutoff
                    if since and published_at < since:
                        logger.info("Reached cutoff date, stopping pagination", extra={"since": since, "published_at": published_at})
                        return videos

                    videos.append(
                        VideoInfo(
                            external_video_id=video_id,
                            title=snippet["title"],
                            video_url=f"https://www.youtube.com/watch?v={video_id}",
                            published_at=published_at,
                            platform="youtube",
                            description=snippet.get("description"),
                            thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url"),
                            # Duration/stats require a separate videos.list call
                        )
                    )

                page_token = response.get("nextPageToken")
                if not page_token:
                    break

            # Enrich with duration + stats via videos.list (batch call, cheap)
            if videos:
                await self._enrich_video_details(videos)

            return videos

        except HttpError as exc:
            if exc.resp.status == 403 and "quotaExceeded" in str(exc):
                raise QuotaExceededError("YouTube Data API quota exceeded") from exc
            raise ExternalServiceError(f"YouTube API error: {exc}") from exc

    async def _enrich_video_details(self, videos: list[VideoInfo]) -> None:
        """Batch-fetch full details (duration, stats, category, tags) via videos.list."""
        video_ids = [v.external_video_id for v in videos]
        # videos.list accepts up to 50 IDs at once
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i : i + 50]
            request = self._youtube.videos().list(
                part="contentDetails,statistics,snippet",
                id=",".join(batch),
            )
            response = request.execute()

            details_map = {item["id"]: item for item in response.get("items", [])}

            for video in videos:
                if video.external_video_id not in details_map:
                    continue
                item = details_map[video.external_video_id]
                content_details = item.get("contentDetails", {})
                stats = item.get("statistics", {})
                snippet = item.get("snippet", {})

                # Parse ISO 8601 duration (e.g., "PT4M13S")
                duration_iso = content_details.get("duration")
                if duration_iso:
                    try:
                        video.duration_seconds = int(isodate.parse_duration(duration_iso).total_seconds())
                    except Exception:
                        pass

                video.language = snippet.get("defaultLanguage") or snippet.get("defaultAudioLanguage")
                video.tags = snippet.get("tags", [])
                video.category = snippet.get("categoryId")
                video.view_count = int(stats.get("viewCount", 0)) if stats.get("viewCount") else None
                video.like_count = int(stats.get("likeCount", 0)) if stats.get("likeCount") else None
                video.comment_count = int(stats.get("commentCount", 0)) if stats.get("commentCount") else None

                # Detect Shorts (duration <= 60s)
                if video.duration_seconds and video.duration_seconds <= 60:
                    video.is_short = True
                    video.content_type = "short"

    async def get_video_stats(self, external_video_ids: list[str]) -> dict[str, dict]:
        """Batch-fetch current view/like/comment counts."""
        results = {}
        try:
            for i in range(0, len(external_video_ids), 50):
                batch = external_video_ids[i : i + 50]
                request = self._youtube.videos().list(
                    part="statistics",
                    id=",".join(batch),
                )
                response = request.execute()

                for item in response.get("items", []):
                    vid = item["id"]
                    stats = item.get("statistics", {})
                    results[vid] = {
                        "view_count": int(stats.get("viewCount", 0)) if stats.get("viewCount") else None,
                        "like_count": int(stats.get("likeCount", 0)) if stats.get("likeCount") else None,
                        "comment_count": int(stats.get("commentCount", 0)) if stats.get("commentCount") else None,
                    }
            return results

        except HttpError as exc:
            if exc.resp.status == 403 and "quotaExceeded" in str(exc):
                raise QuotaExceededError("YouTube Data API quota exceeded") from exc
            raise ExternalServiceError(f"YouTube API error: {exc}") from exc
