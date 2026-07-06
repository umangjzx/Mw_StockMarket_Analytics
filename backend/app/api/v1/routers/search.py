"""
Search endpoints.

GET  /search         — structured filter search (SQL)
POST /search/semantic — natural-language vector search (pgvector)
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.config import settings
from app.schemas.search import (
    SemanticChunkResult,
    SemanticSearchRequest,
    SemanticSearchResponse,
    StructuredSearchResponse,
    VideoSearchResult,
)
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


def _get_provider():
    """Return configured LLM+embedding provider."""
    if settings.LLM_PROVIDER == "ollama":
        from app.providers.llm.ollama_provider import OllamaProvider
        return OllamaProvider()
    from app.providers.llm.openai_provider import OpenAIProvider
    return OpenAIProvider()


@router.get("", response_model=StructuredSearchResponse)
async def structured_search(
    q: str | None = Query(None, description="Keyword search on title/description"),
    ticker: str | None = Query(None, description="Filter by stock ticker, e.g. AAPL"),
    company: str | None = Query(None, description="Filter by company name (partial match)"),
    channel_id: int | None = None,
    creator: str | None = Query(None, description="Filter by channel/creator name (partial match)"),
    topic: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> StructuredSearchResponse:
    service = SearchService(db, _get_provider())

    videos, total = await service.structured_search(
        q=q,
        ticker=ticker,
        company=company,
        channel_id=channel_id,
        creator=creator,
        topic=topic,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )

    return StructuredSearchResponse(
        items=[VideoSearchResult.model_validate(v) for v in videos],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/semantic", response_model=SemanticSearchResponse)
async def semantic_search(
    body: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> SemanticSearchResponse:
    """Natural-language semantic search using pgvector cosine similarity."""
    provider = _get_provider()
    service = SearchService(db, provider)

    filters = body.filters or {}
    results = await service.semantic_search(
        query=body.query,
        top_k=body.top_k,
        video_id=filters.get("video_id"),
        channel_id=filters.get("channel_id"),
        date_from=filters.get("date_from"),
        date_to=filters.get("date_to"),
    )

    chunks = [
        SemanticChunkResult(
            video_id=r["video_id"],
            video_title=r["video_title"],
            external_video_id=r["external_video_id"],
            published_at=r.get("published_at"),
            channel_id=r["channel_id"],
            segment_id=r["segment_id"],
            text=r["text"],
            start_seconds=r.get("start_seconds"),
            end_seconds=r.get("end_seconds"),
            similarity=float(r["similarity"]),
        )
        for r in results
    ]

    return SemanticSearchResponse(
        query=body.query,
        results=chunks,
        total=len(chunks),
    )
