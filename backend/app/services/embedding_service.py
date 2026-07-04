"""
Embedding service — chunks a transcript and generates/stores pgvector embeddings.

Memory-efficient: embeds and saves one batch at a time, never accumulates
all vectors in memory simultaneously. Avoids SIGKILL on large transcripts.
"""

import gc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.llm.base import EmbeddingProvider
from app.repositories.embedding_repository import EmbeddingRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.repositories.video_repository import VideoRepository
from app.utils.chunking import chunk_transcript

logger = get_logger(__name__)

EMBED_BATCH_SIZE = 5  # small batches — embed+save+free before moving on


class EmbeddingService:

    def __init__(self, session: AsyncSession, embedder: EmbeddingProvider) -> None:
        self._session = session
        self._embedder = embedder
        self._video_repo = VideoRepository(session)
        self._transcript_repo = TranscriptRepository(session)
        self._embed_repo = EmbeddingRepository(session)

    async def embed_video(self, video_id: int) -> int:
        """
        Chunk the transcript, generate embeddings in batches, upsert into pgvector.
        Returns the number of embeddings stored.
        Advances pipeline: EMBEDDING_PENDING → EMBEDDED → INDEXED.
        """
        await self._video_repo.set_pipeline_status(video_id, "EMBEDDING_PENDING")
        await self._session.commit()

        transcript = await self._transcript_repo.get_by_video_id(
            video_id, with_segments=True
        )
        if not transcript or not transcript.segments:
            logger.warning("No transcript/segments for embedding", extra={"video_id": video_id})
            await self._video_repo.set_pipeline_status(
                video_id, "FAILED", failure_reason="No transcript segments to embed"
            )
            await self._session.commit()
            return 0

        segments = sorted(transcript.segments, key=lambda s: s.sequence_no)
        chunks = chunk_transcript(segments)

        # Free segments from memory — we only need chunks now
        del segments
        del transcript
        gc.collect()

        if not chunks:
            logger.warning("Chunking produced no chunks", extra={"video_id": video_id})
            await self._video_repo.set_pipeline_status(
                video_id, "FAILED", failure_reason="Chunking produced no output"
            )
            await self._session.commit()
            return 0

        total_chunks = len(chunks)
        logger.info(
            "Embedding transcript",
            extra={"video_id": video_id, "chunks": total_chunks},
        )

        model_name = (
            settings.OLLAMA_EMBEDDING_MODEL
            if settings.LLM_PROVIDER == "ollama"
            else settings.OPENAI_EMBEDDING_MODEL
        )

        # First clear any existing embeddings for this video
        from sqlalchemy import delete
        from app.models.embedding import Embedding
        await self._session.execute(
            delete(Embedding).where(Embedding.video_id == video_id)
        )
        await self._session.commit()

        total_saved = 0

        # Process one small batch at a time — embed, save, free memory, repeat
        for batch_start in range(0, total_chunks, EMBED_BATCH_SIZE):
            batch_chunks = chunks[batch_start : batch_start + EMBED_BATCH_SIZE]
            batch_texts = [c.text for c in batch_chunks]
            batch_seg_ids = [c.segment_ids[0] for c in batch_chunks]

            try:
                vectors = await self._embedder.embed(batch_texts)
            except Exception as exc:
                logger.error(
                    f"Embedding batch failed at {batch_start}",
                    extra={"video_id": video_id, "error": str(exc)}
                )
                raise

            # Save this batch immediately
            for idx, vector in enumerate(vectors):
                from app.models.embedding import Embedding as EmbeddingModel
                emb = EmbeddingModel(
                    transcript_segment_id=batch_seg_ids[idx],
                    video_id=video_id,
                    embedding=vector,
                    model_used=model_name,
                )
                self._session.add(emb)

            await self._session.flush()
            await self._session.commit()
            total_saved += len(vectors)

            # Explicitly free this batch's memory
            del batch_texts, batch_seg_ids, vectors
            gc.collect()

            logger.info(
                f"Embedded batch {batch_start//EMBED_BATCH_SIZE + 1}/"
                f"{(total_chunks + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE}",
                extra={"video_id": video_id, "saved": total_saved}
            )

        # Advance pipeline
        await self._video_repo.set_pipeline_status(video_id, "EMBEDDED")
        await self._session.commit()
        await self._video_repo.set_pipeline_status(video_id, "INDEXED")
        await self._session.commit()

        logger.info(
            "Embeddings stored, video INDEXED",
            extra={"video_id": video_id, "embeddings": total_saved},
        )
        return total_saved
