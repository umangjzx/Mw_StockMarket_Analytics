"""
Celery application instance and queue routing configuration.

All tasks must be registered via autodiscover_tasks() pointing to the workers/tasks module.
Queue routing explicitly assigns each task to a named queue so resource-heavy tasks
(transcription) don't starve lighter tasks (discovery, analysis).
"""

from celery import Celery

from app.core.config import settings

# ── Celery instance ──────────────────────────────────────────────────────────

celery_app = Celery(
    "mw_stockmarket",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Basic Celery config
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # ack only after task completes (or fails)
    worker_prefetch_multiplier=1,  # take one task at a time (fair distribution under heavy load)
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,  # run synchronously in tests
)

# Task autodiscovery — scans app.workers.tasks for @celery_app.task decorators
celery_app.autodiscover_tasks(["app.workers.tasks"], force=True)

# Force import to ensure all tasks are registered in the worker process
def _import_all_tasks():
    import app.workers.tasks.discovery_tasks   # noqa: F401
    import app.workers.tasks.analysis_tasks    # noqa: F401
    import app.workers.tasks.transcript_tasks  # noqa: F401
    import app.workers.tasks.embedding_tasks   # noqa: F401
    import app.workers.tasks.report_tasks      # noqa: F401
    import app.workers.tasks.maintenance_tasks # noqa: F401
    import app.workers.tasks.market_data_tasks # noqa: F401

_import_all_tasks()

# ── Queue routing ─────────────────────────────────────────────────────────────

# Task name → queue mapping
# Default queue is 'celery' if not listed here, but we want every task explicitly routed.
celery_app.conf.task_routes = {
    # Discovery: high concurrency, I/O-bound (YouTube API calls)
    "app.workers.tasks.discovery_tasks.poll_channel": {"queue": "discovery"},
    "app.workers.tasks.discovery_tasks.sync_video_metadata": {"queue": "discovery"},
    "app.workers.tasks.discovery_tasks.refresh_video_stats": {"queue": "discovery"},
    "app.workers.tasks.discovery_tasks.process_single_video_url": {"queue": "discovery"},
    # Transcription: low concurrency, CPU/GPU-bound
    "app.workers.tasks.transcript_tasks.fetch_captions": {"queue": "transcription"},
    "app.workers.tasks.transcript_tasks.run_whisper": {"queue": "transcription"},
    # Analysis: high concurrency, I/O-bound (OpenAI calls), rate-limited
    "app.workers.tasks.analysis_tasks.generate_executive_summary": {"queue": "analysis"},
    "app.workers.tasks.analysis_tasks.generate_detailed_summary": {"queue": "analysis"},
    "app.workers.tasks.analysis_tasks.extract_investment_thesis": {"queue": "analysis"},
    "app.workers.tasks.analysis_tasks.extract_companies_and_tickers": {"queue": "analysis"},
    "app.workers.tasks.analysis_tasks.classify_topics": {"queue": "analysis"},
    "app.workers.tasks.analysis_tasks.score_sentiment": {"queue": "analysis"},
    "app.workers.tasks.analysis_tasks.extract_quotes": {"queue": "analysis"},
    "app.workers.tasks.analysis_tasks.extract_key_numbers": {"queue": "analysis"},
    "app.workers.tasks.analysis_tasks.generate_actionable_insights": {"queue": "analysis"},
    "app.workers.tasks.analysis_tasks.mark_analysis_complete": {"queue": "analysis"},
    # Embeddings: medium concurrency, batched OpenAI calls
    "app.workers.tasks.embedding_tasks.chunk_and_embed": {"queue": "embedding"},
    "app.workers.tasks.embedding_tasks.mark_indexed": {"queue": "embedding"},
    # Reports: low concurrency, one job/day
    "app.workers.tasks.report_tasks.generate_daily_report": {"queue": "reports"},
    # Maintenance: low concurrency, scheduled only
    "app.workers.tasks.maintenance_tasks.retry_failed_pipelines": {"queue": "maintenance"},
    "app.workers.tasks.maintenance_tasks.cleanup_media_cache": {"queue": "maintenance"},
    "app.workers.tasks.maintenance_tasks.reset_quota_counters": {"queue": "maintenance"},
    # Market data: scheduled refreshes for the Company Intelligence module
    "app.workers.tasks.market_data_tasks.refresh_watched_quotes": {"queue": "market_data"},
    "app.workers.tasks.market_data_tasks.refresh_daily_bars": {"queue": "market_data"},
    "app.workers.tasks.market_data_tasks.refresh_company_profiles": {"queue": "market_data"},
}

# ── Beat schedule (periodic tasks) ────────────────────────────────────────────

# Default beat schedule — in production, this should be seeded from a database-backed
# scheduler (django-celery-beat style) so /scheduler API endpoints can mutate it at runtime.
# For Phase 0, inline schedule is sufficient.

from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    # "poll-all-channels": {  # disabled — requires YouTube API key
    #     "task": "app.workers.tasks.discovery_tasks.poll_channel",
    #     "schedule": 900.0,
    #     "options": {"queue": "discovery"},
    # },
    "retry-failed-pipelines": {
        "task": "app.workers.tasks.maintenance_tasks.retry_failed_pipelines",
        "schedule": 600.0,  # every 10 minutes
        "options": {"queue": "maintenance"},
    },
    "generate-daily-report": {
        "task": "app.workers.tasks.report_tasks.generate_daily_report",
        "schedule": crontab(hour=6, minute=0),  # daily at 06:00 local (UTC in container)
        "options": {"queue": "reports"},
    },
    "refresh-video-stats": {
        "task": "app.workers.tasks.discovery_tasks.refresh_video_stats",
        "schedule": 3600.0 * 6,  # every 6 hours
        "options": {"queue": "discovery"},
    },
    "cleanup-media-cache": {
        "task": "app.workers.tasks.maintenance_tasks.cleanup_media_cache",
        "schedule": crontab(hour=3, minute=0),  # daily at 03:00
        "options": {"queue": "maintenance"},
    },
    "reset-quota-counters": {
        "task": "app.workers.tasks.maintenance_tasks.reset_quota_counters",
        "schedule": crontab(hour=0, minute=0),  # daily at 00:00 UTC
        "options": {"queue": "maintenance"},
    },
    "refresh-watched-quotes": {
        "task": "app.workers.tasks.market_data_tasks.refresh_watched_quotes",
        "schedule": 60.0 * settings.MARKET_WATCHED_REFRESH_MINUTES,
        "options": {"queue": "market_data"},
    },
    "refresh-daily-bars": {
        "task": "app.workers.tasks.market_data_tasks.refresh_daily_bars",
        "schedule": crontab(hour=1, minute=0),  # daily, after markets close
        "options": {"queue": "market_data"},
    },
    "refresh-company-profiles": {
        "task": "app.workers.tasks.market_data_tasks.refresh_company_profiles",
        "schedule": crontab(day_of_week="sunday", hour=2, minute=0),  # weekly
        "options": {"queue": "market_data"},
    },
}
