"""
Analysis sub-resource endpoints — all mounted under /videos/{video_id}/...

GET /videos/{id}/summary
GET /videos/{id}/thesis
GET /videos/{id}/sentiment
GET /videos/{id}/quotes
GET /videos/{id}/key-numbers
GET /videos/{id}/insights
GET /videos/{id}/companies
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.video_repository import VideoRepository
from app.schemas.analysis import (
    CompaniesResponse,
    CompanyItem,
    InsightResponse,
    InsightsResponse,
    KeyNumberResponse,
    KeyNumbersResponse,
    QuoteResponse,
    QuotesResponse,
    SentimentResponse,
    SummaryResponse,
    ThesisResponse,
    TickerItem,
    TickerSentimentItem,
)

router = APIRouter(tags=["analysis"])

_NOT_READY_MSG = (
    "Analysis not yet available for video {video_id}. "
    "Pipeline status: {status}"
)


async def _require_video(video_id: int, db: AsyncSession) -> None:
    """Raise 404 if video doesn't exist."""
    repo = VideoRepository(db)
    video = await repo.get_by_id(video_id)
    if not video:
        raise NotFoundError(f"Video {video_id} not found")
    return video


@router.get("/videos/{video_id}/summary", response_model=SummaryResponse)
async def get_summary(
    video_id: int,
    db: AsyncSession = Depends(get_db),
) -> SummaryResponse:
    video = await _require_video(video_id, db)
    repo = AnalysisRepository(db)
    summary = await repo.get_summary(video_id)
    if not summary:
        raise NotFoundError(
            _NOT_READY_MSG.format(video_id=video_id, status=video.pipeline_status)
        )
    return SummaryResponse.model_validate(summary)


@router.get("/videos/{video_id}/thesis", response_model=ThesisResponse)
async def get_thesis(
    video_id: int,
    db: AsyncSession = Depends(get_db),
) -> ThesisResponse:
    video = await _require_video(video_id, db)
    repo = AnalysisRepository(db)
    thesis = await repo.get_thesis(video_id)
    if not thesis:
        raise NotFoundError(
            _NOT_READY_MSG.format(video_id=video_id, status=video.pipeline_status)
        )
    return ThesisResponse.model_validate(thesis)


@router.get("/videos/{video_id}/sentiment", response_model=SentimentResponse)
async def get_sentiment(
    video_id: int,
    db: AsyncSession = Depends(get_db),
) -> SentimentResponse:
    video = await _require_video(video_id, db)
    repo = AnalysisRepository(db)
    sentiment = await repo.get_sentiment(video_id)
    if not sentiment:
        raise NotFoundError(
            _NOT_READY_MSG.format(video_id=video_id, status=video.pipeline_status)
        )
    ticker_sentiments = await repo.get_ticker_sentiments(video_id)

    resp = SentimentResponse.model_validate(sentiment)
    resp.ticker_sentiments = [
        TickerSentimentItem.from_orm_obj(ts) for ts in ticker_sentiments
    ]
    return resp


@router.get("/videos/{video_id}/quotes", response_model=QuotesResponse)
async def get_quotes(
    video_id: int,
    db: AsyncSession = Depends(get_db),
) -> QuotesResponse:
    await _require_video(video_id, db)
    repo = AnalysisRepository(db)
    quotes = await repo.get_quotes(video_id)
    return QuotesResponse(
        video_id=video_id,
        quotes=[QuoteResponse.model_validate(q) for q in quotes],
    )


@router.get("/videos/{video_id}/key-numbers", response_model=KeyNumbersResponse)
async def get_key_numbers(
    video_id: int,
    db: AsyncSession = Depends(get_db),
) -> KeyNumbersResponse:
    await _require_video(video_id, db)
    repo = AnalysisRepository(db)
    items = await repo.get_key_numbers(video_id)
    return KeyNumbersResponse(
        video_id=video_id,
        key_numbers=[KeyNumberResponse.from_orm_obj(kn) for kn in items],
    )


@router.get("/videos/{video_id}/insights", response_model=InsightsResponse)
async def get_insights(
    video_id: int,
    db: AsyncSession = Depends(get_db),
) -> InsightsResponse:
    await _require_video(video_id, db)
    repo = AnalysisRepository(db)
    items = await repo.get_insights(video_id)
    return InsightsResponse(
        video_id=video_id,
        insights=[InsightResponse.from_orm_obj(i) for i in items],
    )


@router.get("/videos/{video_id}/companies", response_model=CompaniesResponse)
async def get_companies(
    video_id: int,
    db: AsyncSession = Depends(get_db),
) -> CompaniesResponse:
    await _require_video(video_id, db)
    repo = AnalysisRepository(db)
    video_companies = await repo.get_video_companies(video_id)

    companies = []
    for vc in video_companies:
        companies.append(CompanyItem(
            id=vc.company.id,
            name=vc.company.name,
            sector=vc.company.sector,
            tickers=[
                TickerItem(id=t.id, symbol=t.symbol, exchange=t.exchange)
                for t in vc.company.tickers
            ],
            mention_count=vc.mention_count,
        ))
    return CompaniesResponse(video_id=video_id, companies=companies)
