"""
YouTube captions provider — the fast, free path.

Uses youtube-transcript-api to fetch auto-generated or manual captions.
This is tried first for every video; Whisper is only used as a fallback.
"""

from decimal import Decimal

from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)
from youtube_transcript_api._errors import VideoUnavailable

from app.core.exceptions import TranscriptionError
from app.core.logging import get_logger
from app.providers.transcription.base import (
    TranscriptResult,
    TranscriptSegment,
    TranscriptionProvider,
)

logger = get_logger(__name__)

# Language preference order — try English first, then any available
LANG_PREFERENCE = ["en", "en-US", "en-GB", "en-AU", "en-CA"]


class YouTubeCaptionsProvider(TranscriptionProvider):
    """Fetch captions from YouTube's own caption track."""

    async def transcribe(self, external_video_id: str, video_url: str) -> TranscriptResult:
        """
        Attempt to fetch YouTube captions for the given video.
        Tries the preferred language list, then falls back to the first available.
        Raises TranscriptionError if no captions are available.
        """
        try:
            # List available transcripts
            transcript_list = YouTubeTranscriptApi.list_transcripts(external_video_id)
        except TranscriptsDisabled:
            raise TranscriptionError(
                f"Captions disabled for video {external_video_id}"
            )
        except VideoUnavailable:
            raise TranscriptionError(
                f"Video unavailable: {external_video_id}"
            )
        except Exception as exc:
            raise TranscriptionError(
                f"Failed to list captions for {external_video_id}: {exc}"
            ) from exc

        # Try preferred languages, then fall back to auto-translated English,
        # then just grab whatever is available
        try:
            transcript = transcript_list.find_transcript(LANG_PREFERENCE)
            language = transcript.language_code
        except NoTranscriptFound:
            try:
                # Try auto-translation to English
                transcript = transcript_list.find_generated_transcript(LANG_PREFERENCE)
                language = transcript.language_code
            except NoTranscriptFound:
                try:
                    # Last resort: first available
                    transcript = next(iter(transcript_list))
                    language = transcript.language_code
                except StopIteration:
                    raise TranscriptionError(
                        f"No captions available for video {external_video_id}"
                    )

        try:
            raw_segments = transcript.fetch()
        except Exception as exc:
            raise TranscriptionError(
                f"Failed to fetch caption data for {external_video_id}: {exc}"
            ) from exc

        if not raw_segments:
            raise TranscriptionError(
                f"Empty captions returned for video {external_video_id}"
            )

        segments = []
        for i, entry in enumerate(raw_segments):
            start = Decimal(str(entry.start)).quantize(Decimal("0.01"))
            duration = Decimal(str(entry.duration)).quantize(Decimal("0.01"))
            end = start + duration

            segments.append(TranscriptSegment(
                text=entry.text.strip(),
                start_seconds=start,
                end_seconds=end,
                sequence_no=i,
            ))

        logger.info(
            "YouTube captions fetched",
            extra={
                "video_id": external_video_id,
                "segments": len(segments),
                "language": language,
            },
        )

        return TranscriptResult(
            segments=segments,
            source="youtube_captions",
            language=language,
        )
