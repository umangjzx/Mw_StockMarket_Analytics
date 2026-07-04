"""
Scheduler endpoints — list, trigger, and update Celery Beat jobs.
All require X-Admin-Key header.
"""

from fastapi import APIRouter, Depends, Query
from app.core.celery_app import celery_app
from app.core.security import require_admin_key
from app.core.exceptions import NotFoundError

router = APIRouter(
    prefix="/scheduler",
    tags=["scheduler"],
    dependencies=[Depends(require_admin_key)],
)

# Maps the API-facing job name → (beat schedule key, task name, default queue)
_JOB_MAP = {
    "poll-all-channels":      ("poll-all-channels",      "app.workers.tasks.discovery_tasks.poll_channel",             "discovery"),
    "retry-failed-pipelines": ("retry-failed-pipelines", "app.workers.tasks.maintenance_tasks.retry_failed_pipelines", "maintenance"),
    "generate-daily-report":  ("generate-daily-report",  "app.workers.tasks.report_tasks.generate_daily_report",       "reports"),
    "refresh-video-stats":    ("refresh-video-stats",    "app.workers.tasks.discovery_tasks.refresh_video_stats",      "discovery"),
    "cleanup-media-cache":    ("cleanup-media-cache",    "app.workers.tasks.maintenance_tasks.cleanup_media_cache",    "maintenance"),
    "reset-quota-counters":   ("reset-quota-counters",   "app.workers.tasks.maintenance_tasks.reset_quota_counters",   "maintenance"),
}


@router.get("/jobs")
def list_jobs() -> dict:
    """List all registered Celery Beat periodic jobs with their schedule."""
    beat_schedule = celery_app.conf.beat_schedule or {}
    jobs = []
    for job_name, job_def in beat_schedule.items():
        schedule = job_def.get("schedule")
        schedule_repr = repr(schedule) if schedule else "unknown"
        jobs.append({
            "name": job_name,
            "task": job_def.get("task"),
            "schedule": schedule_repr,
            "options": job_def.get("options", {}),
        })
    return {"jobs": jobs}


@router.post("/jobs/{job_name}/trigger")
def trigger_job(job_name: str) -> dict:
    """Fire a Beat job immediately (out-of-band, does not affect the schedule)."""
    if job_name not in _JOB_MAP:
        raise NotFoundError(f"Job '{job_name}' not found. Known jobs: {list(_JOB_MAP)}")

    _, task_name, queue = _JOB_MAP[job_name]
    result = celery_app.send_task(task_name, queue=queue)
    return {"status": "triggered", "job": job_name, "task_id": result.id, "queue": queue}


@router.patch("/jobs/{job_name}")
def update_job_schedule(
    job_name: str,
    interval_seconds: int = Query(..., ge=60, description="New run interval in seconds"),
) -> dict:
    """
    Update a job's cadence at runtime (writes to the in-memory beat schedule).
    Note: this resets on worker restart. For persistence, back the schedule with a DB.
    """
    if job_name not in _JOB_MAP:
        raise NotFoundError(f"Job '{job_name}' not found")

    beat_key = _JOB_MAP[job_name][0]
    if beat_key not in (celery_app.conf.beat_schedule or {}):
        raise NotFoundError(f"Beat schedule entry '{beat_key}' not registered")

    celery_app.conf.beat_schedule[beat_key]["schedule"] = float(interval_seconds)
    return {
        "status": "updated",
        "job": job_name,
        "new_interval_seconds": interval_seconds,
    }
