"""Video endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import require_admin_key
from app.db.session import get_db
from app.repositories.video_repository import VideoRepository
from app.schemas.video import VideoListResponse, VideoResponse

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("", response_model=VideoListResponse)
async def list_videos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel_id: int | None = None,
    pipeline_status: str | None = None,
    content_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort: str = Query("-published_at", description="Sort field, prefix - for descending"),
    db: AsyncSession = Depends(get_db),
) -> VideoListResponse:
    """List videos with optional filters."""
    repo = VideoRepository(db)
    items, total = await repo.list_paginated(
        page=page,
        page_size=page_size,
        channel_id=channel_id,
        pipeline_status=pipeline_status,
        content_type=content_type,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
    )
    return VideoListResponse(items=items, page=page, page_size=page_size, total=total)


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
) -> VideoResponse:
    """Get video detail: metadata + latest stats."""
    repo = VideoRepository(db)
    video = await repo.get_by_id(video_id)
    if not video:
        raise NotFoundError(f"Video {video_id} not found")
    return VideoResponse.model_validate(video)


@router.post("/process-url")
async def process_video_url(
    url: str = Query(..., description="YouTube video URL to process"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Process a single YouTube video by URL.
    Returns immediately with video_id and task_id for monitoring.
    
    Example: POST /api/v1/videos/process-url?url=https://www.youtube.com/watch?v=dQw4w9WgXcQ
    """
    from app.workers.tasks.discovery_tasks import process_single_video_url
    
    # Extract video ID from URL
    import re
    patterns = [
        r'(?:v=|/)([0-9A-Za-z_-]{11}).*',  # Standard and short URLs
        r'(?:embed/)([0-9A-Za-z_-]{11})',   # Embed URLs
        r'^([0-9A-Za-z_-]{11})$',           # Just the ID
    ]
    
    external_video_id = None
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            external_video_id = match.group(1)
            break
    
    if not external_video_id:
        from app.core.exceptions import ValidationError
        raise ValidationError(f"Could not extract video ID from URL: {url}")
    
    # Check if already exists
    repo = VideoRepository(db)
    existing = await repo.find_by_external_id(external_video_id)
    
    if existing:
        # Re-process existing video
        from app.workers.pipeline import enqueue_pipeline_from
        task_id = enqueue_pipeline_from(existing.id, "DISCOVERED")
        
        return {
            "status": "reprocessing",
            "video_id": existing.id,
            "external_video_id": external_video_id,
            "task_id": task_id,
            "message": "Video already exists, re-triggering pipeline"
        }
    
    # Trigger new video processing
    result = process_single_video_url.delay(url)
    
    return {
        "status": "processing",
        "external_video_id": external_video_id,
        "task_id": result.id,
        "message": "Video processing started. Check status with task_id or poll /api/v1/videos",
        "poll_url": f"/api/v1/videos?external_id={external_video_id}"
    }


@router.post(
    "/{video_id}/reprocess",
    dependencies=[Depends(require_admin_key)],
)
async def reprocess_video(
    video_id: int,
    from_stage: str = Query("TRANSCRIPT_PENDING", description="Pipeline stage to restart from"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Admin: re-enqueue a video's pipeline from a given stage.
    """
    repo = VideoRepository(db)
    video = await repo.get_by_id(video_id)
    if not video:
        raise NotFoundError(f"Video {video_id} not found")

    valid_stages = {
        "TRANSCRIPT_PENDING",
        "ANALYSIS_PENDING",
        "EMBEDDING_PENDING",
        "DISCOVERED",
    }
    if from_stage not in valid_stages:
        from app.core.exceptions import ValidationError
        raise ValidationError(f"Invalid from_stage. Must be one of: {sorted(valid_stages)}")

    await repo.set_pipeline_status(
        video_id=video_id,
        status=from_stage,
        failure_reason=None,
    )

    from app.workers.pipeline import enqueue_pipeline_from
    task_id = enqueue_pipeline_from(video_id, from_stage)

    return {
        "status": "enqueued",
        "video_id": video_id,
        "from_stage": from_stage,
        "task_id": task_id,
    }
