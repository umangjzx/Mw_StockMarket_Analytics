"""
Local Whisper provider using faster-whisper.

Downloads audio via yt-dlp, runs faster-whisper locally.
CPU-bound — routed to the dedicated 'transcription' Celery queue.
Audio is deleted after successful transcription.
"""

import os
import tempfile
from decimal import Decimal

import yt_dlp
from faster_whisper import WhisperModel

from app.core.config import settings
from app.core.exceptions import TranscriptionError
from app.core.logging import get_logger
from app.providers.transcription.base import (
    TranscriptResult,
    TranscriptSegment,
    TranscriptionProvider,
)

logger = get_logger(__name__)

# Module-level model cache — loaded once per worker process
_model_cache: WhisperModel | None = None


def _get_model() -> WhisperModel:
    global _model_cache
    if _model_cache is None:
        logger.info(
            "Loading Whisper model",
            extra={"size": settings.WHISPER_MODEL_SIZE, "device": settings.WHISPER_DEVICE},
        )
        _model_cache = WhisperModel(
            settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type="int8" if settings.WHISPER_DEVICE == "cpu" else "float16",
        )
        logger.info("Whisper model loaded")
    return _model_cache


class WhisperLocalProvider(TranscriptionProvider):
    """
    Transcription via faster-whisper running locally.
    Audio is downloaded with yt-dlp, transcribed, then the file is deleted.
    """

    async def transcribe(self, external_video_id: str, video_url: str) -> TranscriptResult:
        audio_path: str | None = None
        try:
            audio_path = await self._download_audio(video_url, external_video_id)
            return await self._transcribe_file(audio_path, external_video_id)
        except TranscriptionError:
            raise
        except Exception as exc:
            raise TranscriptionError(
                f"Whisper local transcription failed for {external_video_id}: {exc}"
            ) from exc
        finally:
            if audio_path and os.path.exists(audio_path):
                try:
                    os.remove(audio_path)
                    logger.info("Deleted audio cache file", extra={"path": audio_path})
                except OSError:
                    pass

    async def _download_audio(self, video_url: str, video_id: str) -> str:
        """Download audio-only stream via yt-dlp. Returns path to the audio file."""
        cache_dir = settings.MEDIA_CACHE_DIR
        os.makedirs(cache_dir, exist_ok=True)
        output_template = os.path.join(cache_dir, f"{video_id}.%(ext)s")

        ydl_opts = {
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "0",
            }],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
        except Exception as exc:
            raise TranscriptionError(
                f"yt-dlp audio download failed for {video_id}: {exc}"
            ) from exc

        # Find the output file (extension may vary)
        wav_path = os.path.join(cache_dir, f"{video_id}.wav")
        if os.path.exists(wav_path):
            return wav_path

        # Fallback: scan for any file with this video_id
        for fname in os.listdir(cache_dir):
            if fname.startswith(video_id):
                return os.path.join(cache_dir, fname)

        raise TranscriptionError(f"Audio file not found after download for {video_id}")

    async def _transcribe_file(self, audio_path: str, video_id: str) -> TranscriptResult:
        """Run faster-whisper on the audio file, return a TranscriptResult."""
        model = _get_model()

        logger.info("Running Whisper transcription", extra={"video_id": video_id, "path": audio_path})

        raw_segments, info = model.transcribe(
            audio_path,
            beam_size=5,
            vad_filter=True,               # Filter out silence
            vad_parameters={"min_silence_duration_ms": 500},
        )

        segments: list[TranscriptSegment] = []
        for i, seg in enumerate(raw_segments):
            segments.append(TranscriptSegment(
                text=seg.text.strip(),
                start_seconds=Decimal(str(round(seg.start, 2))),
                end_seconds=Decimal(str(round(seg.end, 2))),
                sequence_no=i,
            ))

        if not segments:
            raise TranscriptionError(
                f"Whisper returned no segments for {video_id}"
            )

        language = info.language if info else None
        logger.info(
            "Whisper transcription complete",
            extra={"video_id": video_id, "segments": len(segments), "language": language},
        )

        return TranscriptResult(
            segments=segments,
            source="whisper_local",
            language=language,
        )
