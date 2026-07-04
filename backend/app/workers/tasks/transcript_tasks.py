"""
Transcript tasks — caption fetch (fast path) and Whisper fallback (slow path).

Both tasks share the same TranscriptService waterfall logic. The distinction is:
- fetch_captions: enqueued first; tries YouTube captions THEN Whisper.
  If captions are available this completes in seconds.
- run_whisper: reserved for explicit Whisper-only retries (e.g., after a
  caption-only failure was manually triaged and marked for re-run).
"""

import asyncio

from celery import Task

from app.core.celery_app import celery_app
from app.core.logging import get_logger
from app.db.session import create_worker_session
from app.repositories.video_repository import VideoRepository
from app.services.transcript_service import TranscriptService

logger = get_logger(__name__)


@celery_app.task(
    name="app.workers.tasks.transcript_tasks.fetch_captions",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
)
def fetch_captions(self: Task, video_id: int) -> dict:
    """
    Fetch transcript for a video using the full provider waterfall
    (YouTube captions → Whisper fallback). This is the standard entry point.
    """
    return asyncio.run(_fetch_transcript_async(video_id))


@celery_app.task(
    name="app.workers.tasks.transcript_tasks.run_whisper",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    max_retries=3,
)
def run_whisper(self: Task, video_id: int) -> dict:
    """
    Force Whisper transcription — skips YouTube captions.
    Used when captions are known to be unavailable or of poor quality.
    """
    return asyncio.run(_run_whisper_async(video_id))


async def _fetch_transcript_async(video_id: int) -> dict:
    async with create_worker_session() as session:
        video_repo = VideoRepository(session)
        video = await video_repo.get_by_id(video_id)
        if not video:
            logger.error("Video not found for transcription", extra={"video_id": video_id})
            return {"status": "error", "message": "Video not found", "video_id": video_id}

        service = TranscriptService(session)
        transcript = await service.fetch_or_generate(video)

        # Advance to ANALYSIS_PENDING before releasing the session
        await video_repo.set_pipeline_status(video_id, "ANALYSIS_PENDING")
        await session.commit()

    # Enqueue the analysis chord outside the session
    from app.workers.pipeline import build_analysis_chord
    build_analysis_chord(video_id).apply_async()

    return {
        "status": "ok",
        "video_id": video_id,
        "transcript_id": transcript.id,
        "source": transcript.source,
        "word_count": transcript.word_count,
    }


async def _run_whisper_async(video_id: int) -> dict:
    """Force Whisper-only transcription (skip YouTube captions attempt)."""
    from app.core.config import settings
    from app.core.exceptions import TranscriptionError
    from app.repositories.video_repository import VideoRepository
    from app.repositories.transcript_repository import TranscriptRepository

    async with create_worker_session() as session:
        video_repo = VideoRepository(session)
        video = await video_repo.get_by_id(video_id)
        if not video:
            return {"status": "error", "message": "Video not found", "video_id": video_id}

        await video_repo.set_pipeline_status(video.id, "TRANSCRIPT_PENDING")
        await session.commit()

        if settings.WHISPER_MODE == "openai_api":
            from app.providers.transcription.whisper_api_provider import WhisperAPIProvider
            provider = WhisperAPIProvider()
        else:
            from app.providers.transcription.whisper_local_provider import WhisperLocalProvider
            provider = WhisperLocalProvider()

        try:
            result = await provider.transcribe(
                external_video_id=video.external_video_id,
                video_url=video.video_url,
            )
        except TranscriptionError as exc:
            await video_repo.set_pipeline_status(video.id, "FAILED", failure_reason=str(exc))
            await session.commit()
            return {"status": "error", "video_id": video_id, "error": str(exc)}

        transcript_repo = TranscriptRepository(session)
        transcript = await transcript_repo.save_transcript(
            video_id=video.id,
            source=result.source,
            language=result.language,
            full_text=result.full_text,
            word_count=result.word_count,
            segments=[
                {
                    "sequence_no": s.sequence_no,
                    "start_seconds": s.start_seconds,
                    "end_seconds": s.end_seconds,
                    "text": s.text,
                }
                for s in result.segments
            ],
        )
        await video_repo.set_pipeline_status(video.id, "TRANSCRIPT_READY")
        await session.commit()

        return {
            "status": "ok",
            "video_id": video_id,
            "transcript_id": transcript.id,
            "source": result.source,
            "word_count": result.word_count,
        }
