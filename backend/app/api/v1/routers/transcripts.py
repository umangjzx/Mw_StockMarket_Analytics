"""
Transcript endpoint — mounted under /videos/{video_id}/transcript.

GET  /api/v1/videos/{video_id}/transcript
     Returns full transcript text + paginated segments.

POST /api/v1/videos/{video_id}/transcript/retranscribe   (admin)
     Re-enqueue the transcript task for a video.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import require_admin_key
from app.db.session import get_db
from app.repositories.transcript_repository import TranscriptRepository
from app.repositories.video_repository import VideoRepository
from app.schemas.transcript import TranscriptSegmentListResponse, TranscriptResponse
from app.workers.tasks.transcript_tasks import fetch_captions, run_whisper

router = APIRouter(tags=["transcripts"])


@router.get("/videos/{video_id}/transcript", response_model=TranscriptSegmentListResponse)
async def get_transcript(
    video_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> TranscriptSegmentListResponse:
    """
    Get the full transcript for a video.
    Segments are paginated; use page/page_size to navigate long transcripts.
    """
    video_repo = VideoRepository(db)
    video = await video_repo.get_by_id(video_id)
    if not video:
        raise NotFoundError(f"Video {video_id} not found")

    transcript_repo = TranscriptRepository(db)
    transcript = await transcript_repo.get_by_video_id(video_id)
    if not transcript:
        raise NotFoundError(
            f"Transcript not available for video {video_id}. "
            f"Pipeline status: {video.pipeline_status}"
        )

    segments = await transcript_repo.get_segments(
        transcript_id=transcript.id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    total = await transcript_repo.count_segments(transcript.id)

    return TranscriptSegmentListResponse(
        transcript=TranscriptResponse.model_validate(transcript),
        segments=segments,
        page=page,
        page_size=page_size,
        total_segments=total,
    )


@router.post(
    "/videos/{video_id}/transcript/retranscribe",
    dependencies=[Depends(require_admin_key)],
)
async def retranscribe(
    video_id: int,
    force_whisper: bool = Query(False, description="Skip YouTube captions, go straight to Whisper"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Admin: re-enqueue transcript task for a video (e.g., after a failed attempt)."""
    video_repo = VideoRepository(db)
    video = await video_repo.get_by_id(video_id)
    if not video:
        raise NotFoundError(f"Video {video_id} not found")

    if force_whisper:
        task = run_whisper.apply_async(args=[video_id], queue="transcription")
    else:
        task = fetch_captions.apply_async(args=[video_id], queue="transcription")

    return {
        "status": "enqueued",
        "video_id": video_id,
        "task_id": task.id,
        "force_whisper": force_whisper,
    }
