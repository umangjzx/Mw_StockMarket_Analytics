"""
AI analysis tasks — each extractor is an independent Celery task.

All run in parallel via a Celery chord (see pipeline.py).
Each task:
- Is independently retryable with exponential backoff
- Calls exactly one AnalysisService method
- Commits its own changes so a partial failure doesn't lose completed work
"""

import asyncio

from celery import Task

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)

_RETRY_KWARGS = dict(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)


def _make_task(name: str, method: str):
    """Factory that creates a bound analysis task calling service.<method>."""
    @celery_app.task(name=name, bind=True, **_RETRY_KWARGS)
    def _task(self: Task, video_id: int) -> dict:
        return asyncio.run(_run(video_id, method))
    return _task


async def _run(video_id: int, method: str) -> dict:
    from app.db.session import create_worker_session
    from app.core.config import settings
    from app.services.analysis_service import AnalysisService
    import asyncio, random

    await asyncio.sleep(random.uniform(0.05, 0.3))

    if settings.LLM_PROVIDER == "ollama":
        from app.providers.llm.ollama_provider import OllamaProvider
        llm = OllamaProvider()
    else:
        from app.providers.llm.openai_provider import OpenAIProvider
        llm = OpenAIProvider()

    async with create_worker_session() as session:
        service = AnalysisService(session, llm)
        fn = getattr(service, f"run_{method}")
        result = await fn(video_id)
        await session.commit()
        return result


# Register all 8 extractor tasks
generate_executive_summary = _make_task(
    "app.workers.tasks.analysis_tasks.generate_executive_summary", "summary"
)
generate_detailed_summary = _make_task(
    # detailed_summary is part of the same summary run — maps to same method
    "app.workers.tasks.analysis_tasks.generate_detailed_summary", "summary"
)
extract_investment_thesis = _make_task(
    "app.workers.tasks.analysis_tasks.extract_investment_thesis", "thesis"
)
extract_companies_and_tickers = _make_task(
    "app.workers.tasks.analysis_tasks.extract_companies_and_tickers", "entities"
)
classify_topics = _make_task(
    "app.workers.tasks.analysis_tasks.classify_topics", "topics"
)
score_sentiment = _make_task(
    "app.workers.tasks.analysis_tasks.score_sentiment", "sentiment"
)
extract_quotes = _make_task(
    "app.workers.tasks.analysis_tasks.extract_quotes", "quotes"
)
extract_key_numbers = _make_task(
    "app.workers.tasks.analysis_tasks.extract_key_numbers", "key_numbers"
)
generate_actionable_insights = _make_task(
    "app.workers.tasks.analysis_tasks.generate_actionable_insights", "insights"
)


@celery_app.task(
    name="app.workers.tasks.analysis_tasks.mark_analysis_complete",
    bind=True,
)
def mark_analysis_complete(self: Task, results: list, video_id: int) -> dict:
    """
    Chord callback — fires after all 9 analysis tasks finish (pass or fail).
    Advances pipeline status to ANALYZED, then enqueues the embedding stage.
    """
    return asyncio.run(_mark_complete(results, video_id))


async def _mark_complete(results: list, video_id: int) -> dict:
    from app.db.session import create_worker_session
    from app.repositories.video_repository import VideoRepository

    failed = [r for r in results if isinstance(r, dict) and not r.get("ok")]
    ok_count = len(results) - len(failed)

    async with create_worker_session() as session:
        repo = VideoRepository(session)

        if failed:
            logger.warning(
                "Some analysis tasks failed",
                extra={"video_id": video_id, "failed": failed},
            )

        # Advance to ANALYZED even if some tasks failed — partial analysis is still useful.
        # Failed extractors surface via /admin/pipeline/failures with the specific reason.
        await repo.set_pipeline_status(video_id, "ANALYZED")
        await session.commit()

    logger.info(
        "Analysis complete",
        extra={"video_id": video_id, "ok": ok_count, "failed": len(failed)},
    )

    # Enqueue embedding stage
    from app.workers.tasks.embedding_tasks import chunk_and_embed
    chunk_and_embed.apply_async(args=[video_id], queue="embedding")

    return {
        "video_id": video_id,
        "status": "ANALYZED",
        "ok_tasks": ok_count,
        "failed_tasks": len(failed),
    }
