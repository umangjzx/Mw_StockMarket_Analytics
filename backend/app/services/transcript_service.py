"""
Transcript service — orchestrates provider waterfall for a single video.

Waterfall order:
  1. YouTube captions (free, fast, usually good enough)
  2. Whisper local / Whisper API (fallback, configured via WHISPER_MODE)

Both paths produce the same TranscriptResult shape which is then persisted
with full timestamped segments.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TranscriptionError
from app.core.logging import get_logger
from app.models.transcript import Transcript
from app.models.video import Video
from app.providers.transcription.base import TranscriptionProvider
from app.providers.transcription.youtube_captions_provider import YouTubeCaptionsProvider
from app.repositories.transcript_repository import TranscriptRepository
from app.repositories.video_repository import VideoRepository

logger = get_logger(__name__)


def _build_whisper_provider() -> TranscriptionProvider:
    """Instantiate the configured Whisper provider."""
    from app.core.config import settings
    if settings.WHISPER_MODE == "groq":
        from app.providers.transcription.groq_provider import GroqWhisperProvider
        return GroqWhisperProvider()
    elif settings.WHISPER_MODE == "openai_api":
        from app.providers.transcription.whisper_api_provider import WhisperAPIProvider
        return WhisperAPIProvider()
    else:
        from app.providers.transcription.whisper_local_provider import WhisperLocalProvider
        return WhisperLocalProvider()


class TranscriptService:
    """Fetches or generates a transcript for a video and persists it."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._transcript_repo = TranscriptRepository(session)
        self._video_repo = VideoRepository(session)

    async def fetch_or_generate(self, video: Video) -> Transcript:
        """
        Try to get a transcript, in waterfall order:
          1. YouTube captions (fast, free)
          2. Configured Whisper provider (local or OpenAI API)

        Updates pipeline_status throughout. Returns the persisted Transcript.
        """
        # Mark pipeline as TRANSCRIPT_PENDING so the status is visible while we work
        await self._video_repo.set_pipeline_status(video.id, "TRANSCRIPT_PENDING")
        await self._session.commit()

        transcript_result = None
        last_error: Exception | None = None

        # ── Step 1: YouTube captions ─────────────────────────────────────────
        try:
            captions_provider = YouTubeCaptionsProvider()
            transcript_result = await captions_provider.transcribe(
                external_video_id=video.external_video_id,
                video_url=video.video_url,
            )
            logger.info(
                "Transcript obtained via YouTube captions",
                extra={"video_id": video.id, "segments": len(transcript_result.segments)},
            )
        except TranscriptionError as exc:
            logger.info(
                "YouTube captions unavailable, trying Whisper",
                extra={"video_id": video.id, "reason": str(exc)},
            )
            last_error = exc

        # ── Step 2: Whisper fallback ─────────────────────────────────────────
        if transcript_result is None:
            try:
                whisper_provider = _build_whisper_provider()
                transcript_result = await whisper_provider.transcribe(
                    external_video_id=video.external_video_id,
                    video_url=video.video_url,
                )
                logger.info(
                    "Transcript obtained via Whisper",
                    extra={"video_id": video.id, "source": transcript_result.source},
                )
            except TranscriptionError as exc:
                last_error = exc
                logger.error(
                    "All transcription methods failed",
                    extra={"video_id": video.id, "error": str(exc)},
                )

        if transcript_result is None:
            await self._video_repo.set_pipeline_status(
                video.id,
                "FAILED",
                failure_reason=f"Transcription failed: {last_error}",
            )
            await self._session.commit()
            raise TranscriptionError(
                f"Could not transcribe video {video.id}: {last_error}"
            )

        # ── Persist ──────────────────────────────────────────────────────────
        seg_dicts = [
            {
                "sequence_no": seg.sequence_no,
                "start_seconds": seg.start_seconds,
                "end_seconds": seg.end_seconds,
                "text": seg.text,
            }
            for seg in transcript_result.segments
        ]

        transcript = await self._transcript_repo.save_transcript(
            video_id=video.id,
            source=transcript_result.source,
            language=transcript_result.language,
            full_text=transcript_result.full_text,
            word_count=transcript_result.word_count,
            segments=seg_dicts,
        )

        # Advance pipeline state to TRANSCRIPT_READY
        await self._video_repo.set_pipeline_status(video.id, "TRANSCRIPT_READY")
        await self._session.commit()

        logger.info(
            "Transcript persisted",
            extra={
                "video_id": video.id,
                "transcript_id": transcript.id,
                "source": transcript_result.source,
                "word_count": transcript_result.word_count,
                "segments": len(seg_dicts),
            },
        )
        return transcript
