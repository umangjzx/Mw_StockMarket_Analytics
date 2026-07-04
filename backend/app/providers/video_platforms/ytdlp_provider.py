"""
yt-dlp metadata provider — NO API KEY NEEDED.

Uses yt-dlp to fetch video/channel metadata directly.
Free, no quota limits, no account required.
"""

from datetime import datetime
import yt_dlp

from app.core.logging import get_logger
from app.providers.video_platforms.base import ChannelInfo, VideoInfo

logger = get_logger(__name__)


class YtdlpProvider:
    """
    Fetch YouTube video/channel metadata using yt-dlp (scraping-based).
    No API key needed, no quota limits.
    """

    async def get_video_info(self, video_url: str) -> tuple[VideoInfo, ChannelInfo]:
        """
        Fetch full video + channel metadata from a YouTube URL.
        Returns (VideoInfo, ChannelInfo) ready for DB insertion.
        """
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,  # Get full details
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)

            if not info:
                raise ValueError(f"Could not extract info from {video_url}")

            # Parse timestamps — strip timezone to match DB TIMESTAMP WITHOUT TIME ZONE columns
            upload_date_str = info.get("upload_date")  # YYYYMMDD
            if upload_date_str:
                published_at = datetime.strptime(upload_date_str, "%Y%m%d")  # naive UTC
            else:
                published_at = datetime.utcnow()

            # Build VideoInfo
            video_info = VideoInfo(
                external_video_id=info["id"],
                title=info.get("title", "Untitled"),
                video_url=video_url,
                published_at=published_at,
                platform="youtube",
                description=info.get("description"),
                thumbnail_url=info.get("thumbnail"),
                duration_seconds=info.get("duration"),
                language=info.get("language"),
                tags=info.get("tags", []),
                category=info.get("categories", [None])[0] if info.get("categories") else None,
                content_type="short" if info.get("duration", 0) <= 60 else "video",
                view_count=info.get("view_count"),
                like_count=info.get("like_count"),
                comment_count=info.get("comment_count"),
                is_short=info.get("duration", 0) <= 60,
            )

            # Build ChannelInfo
            channel_info = ChannelInfo(
                external_channel_id=info.get("channel_id", ""),
                display_name=info.get("uploader") or info.get("channel", "Unknown"),
                platform="youtube",
                handle=info.get("uploader_id"),  # e.g., "@CNBC"
                description=info.get("channel_description"),
                thumbnail_url=info.get("channel_thumbnail_url"),
                subscriber_count=info.get("channel_follower_count"),
            )

            logger.info(
                f"Extracted metadata via yt-dlp: {video_info.title}",
                extra={"video_id": video_info.external_video_id, "channel_name": channel_info.display_name}
            )

            return video_info, channel_info

        except Exception as exc:
            raise ValueError(f"yt-dlp extraction failed for {video_url}: {exc}") from exc
