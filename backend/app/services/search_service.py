"""
Search service — structured filter search + semantic (vector) search.

Structured search: SQL over videos with filters (ticker, company, topic, date, channel).
Semantic search: embed query → pgvector cosine similarity → return ranked segments.
"""

from datetime import datetime

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.company import Company, Ticker, VideoCompany
from app.models.topic import Topic, VideoTopic
from app.models.video import Video
from app.providers.llm.base import EmbeddingProvider
from app.repositories.embedding_repository import EmbeddingRepository
from app.repositories.video_repository import VideoRepository

logger = get_logger(__name__)


class SearchService:

    def __init__(self, session: AsyncSession, embedder: EmbeddingProvider) -> None:
        self._session = session
        self._embedder = embedder
        self._video_repo = VideoRepository(session)
        self._embed_repo = EmbeddingRepository(session)

    async def structured_search(
        self,
        q: str | None = None,
        ticker: str | None = None,
        company: str | None = None,
        channel_id: int | None = None,
        topic: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Video], int]:
        """
        SQL-based structured search across videos.
        Returns (videos, total_count).
        """
        from sqlalchemy import func, or_

        q_base = select(Video).where(Video.pipeline_status == "INDEXED")
        count_base = select(func.count()).select_from(Video).where(
            Video.pipeline_status == "INDEXED"
        )

        filters = []

        # Full-text search on title + description
        if q:
            filters.append(
                or_(
                    Video.title.ilike(f"%{q}%"),
                    Video.description.ilike(f"%{q}%"),
                )
            )

        if channel_id:
            filters.append(Video.channel_id == channel_id)

        if date_from:
            filters.append(Video.published_at >= date_from)
        if date_to:
            filters.append(Video.published_at <= date_to)

        if ticker:
            # Join through companies → tickers → video_companies
            ticker_subq = (
                select(VideoCompany.video_id)
                .join(Company, Company.id == VideoCompany.company_id)
                .join(Ticker, Ticker.company_id == Company.id)
                .where(Ticker.symbol.ilike(ticker.upper()))
                .scalar_subquery()
            )
            filters.append(Video.id.in_(ticker_subq))

        if company:
            company_subq = (
                select(VideoCompany.video_id)
                .join(Company, Company.id == VideoCompany.company_id)
                .where(Company.name.ilike(f"%{company}%"))
                .scalar_subquery()
            )
            filters.append(Video.id.in_(company_subq))

        if topic:
            topic_subq = (
                select(VideoTopic.video_id)
                .join(Topic, Topic.id == VideoTopic.topic_id)
                .where(Topic.name.ilike(f"%{topic}%"))
                .scalar_subquery()
            )
            filters.append(Video.id.in_(topic_subq))

        if filters:
            q_base = q_base.where(and_(*filters))
            count_base = count_base.where(and_(*filters))

        q_base = q_base.order_by(Video.published_at.desc()).limit(page_size).offset(
            (page - 1) * page_size
        )

        result = await self._session.execute(q_base)
        count_result = await self._session.execute(count_base)

        return list(result.scalars().all()), count_result.scalar() or 0

    async def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        video_id: int | None = None,
        channel_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[dict]:
        """
        Embed query, run pgvector cosine similarity, return ranked chunks with metadata.
        Each result includes video context for citation.
        """
        vectors = await self._embedder.embed([query])
        query_vector = vectors[0]

        results = await self._embed_repo.similarity_search(
            query_vector=query_vector,
            top_k=top_k,
            video_id=video_id,
            channel_id=channel_id,
            date_from=date_from.replace(tzinfo=None).isoformat() if date_from else None,
            date_to=date_to.replace(tzinfo=None).isoformat() if date_to else None,
        )

        logger.info(
            "Semantic search",
            extra={"query": query[:80], "results": len(results), "top_k": top_k},
        )
        return results
