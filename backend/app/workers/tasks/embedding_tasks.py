"""Embedding tasks — chunk transcript and upsert pgvector embeddings."""

import asyncio

from celery import Task

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


@celery_app.task(
    name="app.workers.tasks.embedding_tasks.chunk_and_embed",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def chunk_and_embed(self: Task, video_id: int) -> dict:
    """Chunk the transcript and generate pgvector embeddings. Advances to INDEXED."""
    return asyncio.run(_embed_async(video_id))


async def _embed_async(video_id: int) -> dict:
    from app.db.session import create_worker_session
    from app.core.config import settings
    from app.services.embedding_service import EmbeddingService

    if settings.LLM_PROVIDER == "ollama":
        from app.providers.llm.ollama_provider import OllamaProvider
        embedder = OllamaProvider()
    else:
        from app.providers.llm.openai_provider import OpenAIProvider
        embedder = OpenAIProvider()

    async with create_worker_session() as session:
        service = EmbeddingService(session, embedder)
        count = await service.embed_video(video_id)
        return {"status": "ok", "video_id": video_id, "embeddings": count}


@celery_app.task(
    name="app.workers.tasks.embedding_tasks.mark_indexed",
    bind=True,
)
def mark_indexed(self: Task, video_id: int) -> dict:
    """Explicitly mark a video INDEXED (used if embedding ran outside the service)."""
    return asyncio.run(_mark_indexed_async(video_id))


async def _mark_indexed_async(video_id: int) -> dict:
    from app.db.session import create_worker_session
    from app.repositories.video_repository import VideoRepository

    async with create_worker_session() as session:
        repo = VideoRepository(session)
        await repo.set_pipeline_status(video_id, "INDEXED")
        await session.commit()
    return {"status": "ok", "video_id": video_id}
