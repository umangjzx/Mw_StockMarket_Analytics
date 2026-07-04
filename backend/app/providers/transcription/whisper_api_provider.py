"""
OpenAI Whisper API provider — burst capacity fallback.

Used when WHISPER_MODE=openai_api or when local Whisper is unavailable.
Downloads audio via yt-dlp, sends to OpenAI Audio API, returns segments.
Audio is deleted after successful transcription.
OpenAI Whisper API does not return word-level timestamps in the standard
response, so segments are sentence-split from the verbose_json output.
"""

import os
from decimal import Decimal

import yt_dlp
from openai import AsyncOpenAI

from app.core.config import settings
from app.core.exceptions import TranscriptionError
from app.core.logging import get_logger
from app.providers.transcription.base import (
    TranscriptResult,
    TranscriptSegment,
    TranscriptionProvider,
)

logger = get_logger(__name__)


class WhisperAPIProvider(TranscriptionProvider):
    """
    Transcription via OpenAI's hosted Whisper API.
    Useful for burst capacity or when a GPU worker is unavailable.
    """

    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not configured")
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def transcribe(self, external_video_id: str, video_url: str) -> TranscriptResult:
        audio_path: str | None = None
        try:
            audio_path = await self._download_audio(video_url, external_video_id)
            return await self._transcribe_via_api(audio_path, external_video_id)
        except TranscriptionError:
            raise
        except Exception as exc:
            raise TranscriptionError(
                f"Whisper API transcription failed for {external_video_id}: {exc}"
            ) from exc
        finally:
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                except OSError:
                    pass

    async def _download_audio(self, video_url: str, video_id: str) -> str:
        """Download audio-only stream via yt-dlp."""
        cache_dir = settings.MEDIA_CACHE_DIR
        os.makedirs(cache_dir, exist_ok=True)
        output_template = os.path.join(cache_dir, f"{video_id}_api.%(ext)s")

        # OpenAI Whisper API accepts: mp3, mp4, mpeg, mpga, m4a, wav, webm
        # We target m4a (small, widely supported)
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
        except Exception as exc:
            raise TranscriptionError(
                f"yt-dlp download failed for {video_id}: {exc}"
            ) from exc

        # Find downloaded file
        for ext in ("m4a", "webm", "mp4", "wav"):
            path = os.path.join(cache_dir, f"{video_id}_api.{ext}")
            if os.path.exists(path):
                return path

        for fname in os.listdir(cache_dir):
            if fname.startswith(f"{video_id}_api"):
                return os.path.join(cache_dir, fname)

        raise TranscriptionError(f"Audio file not found after download for {video_id}")

    async def _transcribe_via_api(self, audio_path: str, video_id: str) -> TranscriptResult:
        """Send audio file to OpenAI Whisper API with verbose_json for segments."""
        logger.info("Sending to OpenAI Whisper API", extra={"video_id": video_id})

        with open(audio_path, "rb") as f:
            response = await self._client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

        raw_segments = response.segments or []

        if not raw_segments:
            # No segment info — return the full text as one segment
            full_text = response.text or ""
            if not full_text.strip():
                raise TranscriptionError(f"OpenAI Whisper returned empty transcript for {video_id}")
            return TranscriptResult(
                segments=[TranscriptSegment(
                    text=full_text.strip(),
                    start_seconds=Decimal("0.00"),
                    end_seconds=Decimal("0.00"),
                    sequence_no=0,
                )],
                source="whisper_api",
                language=response.language,
            )

        segments: list[TranscriptSegment] = []
        for i, seg in enumerate(raw_segments):
            segments.append(TranscriptSegment(
                text=seg.text.strip(),
                start_seconds=Decimal(str(round(seg.start, 2))),
                end_seconds=Decimal(str(round(seg.end, 2))),
                sequence_no=i,
            ))

        logger.info(
            "OpenAI Whisper API transcription complete",
            extra={"video_id": video_id, "segments": len(segments), "language": response.language},
        )

        return TranscriptResult(
            segments=segments,
            source="whisper_api",
            language=response.language,
        )
