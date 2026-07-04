"""
Admin endpoints — pipeline status, failures, retry, quota, task logs.
All require X-Admin-Key header.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin_key
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.task_log import TaskLog
from app.models.video import Video
from app.repositories.video_repository import VideoRepository
from app.services.quota_tracker import QuotaTracker

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_key)],
)


@router.get("/pipeline/status")
async def pipeline_status(db: AsyncSession = Depends(get_db)) -> dict:
    """Counts of videos by pipeline_status."""
    repo = VideoRepository(db)
    counts = await repo.count_by_status()
    total = sum(counts.values())
    return {
        "total": total,
        "counts": [{"status": k, "count": v} for k, v in sorted(counts.items())],
    }


@router.get("/pipeline/failures")
async def pipeline_failures(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List FAILED videos with failure reason and retry count."""
    from app.core.config import settings
    repo = VideoRepository(db)
    items, total = await repo.list_failed(page=page, page_size=page_size)
    return {
        "items": [
            {
                "id": v.id,
                "external_video_id": v.external_video_id,
                "title": v.title,
                "channel_id": v.channel_id,
                "failure_reason": v.pipeline_failure_reason,
                "retry_count": v.pipeline_retry_count,
                "next_retry_at": v.pipeline_next_retry_at,
            }
            for v in items
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post("/pipeline/retry/{video_id}")
async def retry_video(
    video_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually re-enqueue a failed video from its current failure point."""
    repo = VideoRepository(db)
    video = await repo.get_by_id(video_id)
    if not video:
        raise NotFoundError(f"Video {video_id} not found")

    from app.workers.pipeline import enqueue_pipeline_from
    # Reset to TRANSCRIPT_PENDING for a full retry
    await repo.set_pipeline_status(video_id, "TRANSCRIPT_PENDING", failure_reason=None)
    task_id = enqueue_pipeline_from(video_id, "TRANSCRIPT_PENDING")

    return {"status": "enqueued", "video_id": video_id, "task_id": task_id}


@router.get("/quota")
def get_quota() -> dict:
    """Current YouTube API + OpenAI quota/spend tracking."""
    tracker = QuotaTracker()
    current = tracker.get_current_usage()
    from app.core.config import settings
    return {
        "youtube": {
            "used": current,
            "limit": settings.YOUTUBE_DAILY_QUOTA_LIMIT,
            "remaining": settings.YOUTUBE_DAILY_QUOTA_LIMIT - current,
            "pct_used": round(current / settings.YOUTUBE_DAILY_QUOTA_LIMIT * 100, 1),
        },
    }


@router.get("/task-logs")
async def list_task_logs(
    task_name: str | None = None,
    status: str | None = None,
    video_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Query task_logs with optional filters."""
    from sqlalchemy import and_
    filters = []
    if task_name:
        filters.append(TaskLog.task_name.ilike(f"%{task_name}%"))
    if status:
        filters.append(TaskLog.status == status)
    if video_id:
        filters.append(TaskLog.video_id == video_id)
    if date_from:
        filters.append(TaskLog.started_at >= date_from)
    if date_to:
        filters.append(TaskLog.started_at <= date_to)

    q = select(TaskLog).order_by(TaskLog.started_at.desc())
    count_q = select(func.count()).select_from(TaskLog)
    if filters:
        q = q.where(and_(*filters))
        count_q = count_q.where(and_(*filters))
    q = q.limit(page_size).offset((page - 1) * page_size)

    results = await db.execute(q)
    count_result = await db.execute(count_q)
    logs = results.scalars().all()

    return {
        "items": [
            {
                "id": log.id,
                "task_name": log.task_name,
                "video_id": log.video_id,
                "channel_id": log.channel_id,
                "celery_task_id": log.celery_task_id,
                "status": log.status,
                "error_message": log.error_message,
                "duration_ms": log.duration_ms,
                "started_at": log.started_at,
                "finished_at": log.finished_at,
            }
            for log in logs
        ],
        "page": page,
        "page_size": page_size,
        "total": count_result.scalar() or 0,
    }


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List users (admin only)."""
    from app.models.user import User
    count_r = await db.execute(select(func.count()).select_from(User))
    total = count_r.scalar() or 0

    result = await db.execute(
        select(User).order_by(User.id).limit(page_size).offset((page - 1) * page_size)
    )
    users = result.scalars().all()
    return {
        "items": [
            {"id": u.id, "email": u.email, "display_name": u.display_name, "role": u.role, "created_at": u.created_at}
            for u in users
        ],
        "page": page, "page_size": page_size, "total": total,
    }
