"""
Groq Whisper API provider — FREE, ultra-fast transcription.

Groq provides free access to Whisper large-v3 with incredible speed (10x faster than OpenAI).
Downloads audio via yt-dlp, sends to Groq API, returns segments.
Audio is deleted after successful transcription.

Get free API key at: https://console.groq.com/
"""

import os
from decimal import Decimal

import yt_dlp
from groq import AsyncGroq

from app.core.config import settings
from app.core.exceptions import TranscriptionError
from app.core.logging import get_logger
from app.providers.transcription.base import (
    TranscriptResult,
    TranscriptSegment,
    TranscriptionProvider,
)

logger = get_logger(__name__)


class GroqWhisperProvider(TranscriptionProvider):
    """
    Transcription via Groq's ultra-fast Whisper API.
    FREE tier: 7000 requests/day, much faster than OpenAI.
    Uses whisper-large-v3 model for best accuracy.
    """

    def __init__(self) -> None:
        api_key = os.getenv("GROQ_API_KEY") or settings.GROQ_API_KEY
        if not api_key:
            raise ValueError("GROQ_API_KEY not configured")
        self._client = AsyncGroq(api_key=api_key)

    async def transcribe(self, external_video_id: str, video_url: str) -> TranscriptResult:
        audio_path: str | None = None
        try:
            audio_path = await self._download_audio(video_url, external_video_id)
            return await self._transcribe_via_groq(audio_path, external_video_id)
        except TranscriptionError:
            raise
        except Exception as exc:
            raise TranscriptionError(
                f"Groq Whisper transcription failed for {external_video_id}: {exc}"
            ) from exc
        finally:
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                    logger.debug(f"Cleaned up audio file: {audio_path}")
                except OSError:
                    pass

    async def _download_audio(self, video_url: str, video_id: str) -> str:
        """Download audio-only stream via yt-dlp."""
        cache_dir = settings.MEDIA_CACHE_DIR
        os.makedirs(cache_dir, exist_ok=True)
        output_template = os.path.join(cache_dir, f"{video_id}_groq.%(ext)s")

        # Groq accepts: flac, mp3, mp4, mpeg, mpga, m4a, ogg, wav, webm
        # We target m4a (small, good quality)
        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
        }

        logger.info(f"Downloading audio for video {video_id}...")
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
        except Exception as exc:
            raise TranscriptionError(
                f"yt-dlp download failed for {video_id}: {exc}"
            ) from exc

        # Find downloaded file
        for ext in ("m4a", "webm", "mp4", "wav", "mp3"):
            path = os.path.join(cache_dir, f"{video_id}_groq.{ext}")
            if os.path.exists(path):
                file_size = os.path.getsize(path) / (1024 * 1024)  # MB
                logger.info(f"Audio downloaded: {path} ({file_size:.2f} MB)")
                return path

        # Fallback: search for any file matching the prefix
        for fname in os.listdir(cache_dir):
            if fname.startswith(f"{video_id}_groq"):
                return os.path.join(cache_dir, fname)

        raise TranscriptionError(f"Audio file not found after download for {video_id}")

    async def _transcribe_via_groq(self, audio_path: str, video_id: str) -> TranscriptResult:
        """Send audio file to Groq Whisper API with verbose_json for segments."""
        logger.info(f"Sending to Groq Whisper API: {video_id}")

        # Check file size (Groq has 25MB limit)
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        if file_size_mb > 25:
            raise TranscriptionError(
                f"Audio file too large for Groq API: {file_size_mb:.2f}MB (limit: 25MB)."
            )

        with open(audio_path, "rb") as f:
            response = await self._client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                language="en",
            )

        # Groq verbose_json response — segments may be dicts or objects
        raw_segments = getattr(response, "segments", None) or []

        # Normalise: each seg can be a dict or an object with .text / .start / .end
        def _get(seg, key):
            return seg[key] if isinstance(seg, dict) else getattr(seg, key)

        if not raw_segments:
            full_text = getattr(response, "text", "") or ""
            if not full_text.strip():
                raise TranscriptionError(f"Groq Whisper returned empty transcript for {video_id}")

            logger.warning("No segments returned, using full text as single segment")
            return TranscriptResult(
                segments=[TranscriptSegment(
                    text=full_text.strip(),
                    start_seconds=Decimal("0.00"),
                    end_seconds=Decimal("0.00"),
                    sequence_no=0,
                )],
                source="groq_whisper",
                language=getattr(response, "language", None) or "en",
            )

        segments: list[TranscriptSegment] = []
        for i, seg in enumerate(raw_segments):
            text = _get(seg, "text")
            start = _get(seg, "start")
            end = _get(seg, "end")
            segments.append(TranscriptSegment(
                text=str(text).strip(),
                start_seconds=Decimal(str(round(float(start), 2))),
                end_seconds=Decimal(str(round(float(end), 2))),
                sequence_no=i,
            ))

        language = getattr(response, "language", None) or "en"
        logger.info(f"Groq transcription complete: {len(segments)} segments, language={language}")

        return TranscriptResult(
            segments=segments,
            source="groq_whisper",
            language=language,
        )
