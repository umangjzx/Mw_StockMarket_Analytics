"""Daily report generation task."""

import asyncio
from celery import Task
from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(
    name="app.workers.tasks.report_tasks.generate_daily_report",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=2,
)
def generate_daily_report(self: Task, report_date: str | None = None) -> dict:
    """
    Generate a daily market report.
    report_date: ISO date string 'YYYY-MM-DD'. Defaults to yesterday (UTC) if None.
    """
    return asyncio.run(_generate_async(report_date))


async def _generate_async(report_date_str: str | None) -> dict:
    from datetime import date
    from app.db.session import create_worker_session
    from app.core.config import settings
    from app.services.report_service import ReportService

    target_date = date.fromisoformat(report_date_str) if report_date_str else None

    async with create_worker_session() as session:
        if settings.LLM_PROVIDER == "ollama":
            from app.providers.llm.ollama_provider import OllamaProvider
            llm = OllamaProvider()
        else:
            from app.providers.llm.openai_provider import OpenAIProvider
            llm = OpenAIProvider()
        service = ReportService(session, llm)
        report = await service.generate(target_date)
        await session.commit()

    logger.info("Daily report complete", extra={"date": str(report.report_date), "id": report.id})
    return {"status": "ok", "report_id": report.id, "report_date": str(report.report_date)}
