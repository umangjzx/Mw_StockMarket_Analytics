"""
Company Intelligence endpoints — Phase 1 + Phase 2 + Phase 3.

GET  /companies/resolve                — resolve a ticker/company/keyword query
GET  /companies/{ticker}                — main entry-point page (identity + quote + profile)
GET  /companies/{ticker}/quote          — live market data
GET  /companies/{ticker}/chart          — OHLCV bars for charting
GET  /companies/{ticker}/profile        — company overview
GET  /companies/{ticker}/ratios         — key financial ratios
GET  /companies/{ticker}/financials     — income/balance/cashflow statements
GET  /companies/{ticker}/earnings       — next/previous earnings + AI summary
GET  /companies/{ticker}/technicals     — RSI, MACD, SMA/EMA, Bollinger, ATR, trend
GET  /companies/{ticker}/news           — recent news with AI sentiment/impact scoring
GET  /companies/{ticker}/analyst        — analyst consensus, targets, institutional/insider data
GET  /companies/{ticker}/executive-summary — AI-synthesized briefing across every section
GET  /companies/{ticker}/videos         — videos mentioning this company
GET  /companies/{ticker}/intelligence   — full AI video intelligence bundle + semantic search
POST /companies/{ticker}/chat           — RAG chat scoped to this company's videos
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.providers.market_data.base import CHART_RANGES, STATEMENT_PERIODS, STATEMENT_TYPES
from app.providers.market_data.composite_provider import build_market_data_provider
from app.schemas.company_intelligence import (
    AnalystResponse,
    ChartResponse,
    ChatCitation,
    ChatRequest,
    ChatResponse,
    EarningsResponse,
    ExecutiveSummaryResponse,
    FinancialsResponse,
    IntelligenceResponse,
    NewsResponse,
    OverviewResponse,
    ProfileResponse,
    QuoteResponse,
    RatiosResponse,
    ResolveResponse,
    TechnicalsResponse,
    TickerIdentity,
    VideosResponse,
)
from app.services.company_intelligence_service import CompanyIntelligenceService

router = APIRouter(prefix="/companies", tags=["company-intelligence"])


def _get_llm_provider():
    """Return the configured LLM+embedding provider (same pattern as search.py)."""
    if settings.LLM_PROVIDER == "ollama":
        from app.providers.llm.ollama_provider import OllamaProvider
        return OllamaProvider()
    from app.providers.llm.openai_provider import OpenAIProvider
    return OpenAIProvider()


def _get_service(db: AsyncSession) -> CompanyIntelligenceService:
    llm = _get_llm_provider()
    return CompanyIntelligenceService(
        session=db,
        market_provider=build_market_data_provider(),
        llm=llm,
        embedder=llm,
    )


@router.get("/resolve", response_model=ResolveResponse)
async def resolve(
    q: str = Query(..., description="Ticker symbol, company name, or keyword"),
    db: AsyncSession = Depends(get_db),
) -> ResolveResponse:
    service = _get_service(db)
    candidates = await service.resolve_candidates(q)
    return ResolveResponse(
        query=q,
        candidates=[TickerIdentity.model_validate(c) for c in candidates],
    )


@router.get("/{ticker}", response_model=OverviewResponse)
async def get_overview(ticker: str, db: AsyncSession = Depends(get_db)) -> OverviewResponse:
    service = _get_service(db)
    result = await service.get_overview(ticker)
    return OverviewResponse.model_validate(result)


@router.get("/{ticker}/quote", response_model=QuoteResponse)
async def get_quote(ticker: str, db: AsyncSession = Depends(get_db)) -> QuoteResponse:
    service = _get_service(db)
    result = await service.get_quote(ticker)
    return QuoteResponse.model_validate(result)


@router.get("/{ticker}/chart", response_model=ChartResponse)
async def get_chart(
    ticker: str,
    range: str = Query("1M", description=f"One of {CHART_RANGES}"),
    db: AsyncSession = Depends(get_db),
) -> ChartResponse:
    service = _get_service(db)
    chart_range = range.upper()
    if chart_range not in CHART_RANGES:
        from app.core.exceptions import ValidationError
        raise ValidationError(f"range must be one of {CHART_RANGES}, got {range!r}")
    result = await service.get_chart(ticker, chart_range)
    return ChartResponse.model_validate(result)


@router.get("/{ticker}/profile", response_model=ProfileResponse)
async def get_profile(ticker: str, db: AsyncSession = Depends(get_db)) -> ProfileResponse:
    service = _get_service(db)
    result = await service.get_profile(ticker)
    return ProfileResponse.model_validate(result)


@router.get("/{ticker}/ratios", response_model=RatiosResponse)
async def get_ratios(ticker: str, db: AsyncSession = Depends(get_db)) -> RatiosResponse:
    service = _get_service(db)
    result = await service.get_ratios(ticker)
    return RatiosResponse.model_validate(result)


@router.get("/{ticker}/financials", response_model=FinancialsResponse)
async def get_financials(
    ticker: str,
    statement: str = Query("income", description=f"One of {STATEMENT_TYPES}"),
    period: str = Query("annual", description=f"One of {STATEMENT_PERIODS}"),
    db: AsyncSession = Depends(get_db),
) -> FinancialsResponse:
    service = _get_service(db)
    result = await service.get_financials(ticker, statement, period)
    return FinancialsResponse.model_validate(result)


@router.get("/{ticker}/earnings", response_model=EarningsResponse)
async def get_earnings(ticker: str, db: AsyncSession = Depends(get_db)) -> EarningsResponse:
    service = _get_service(db)
    result = await service.get_earnings(ticker)
    return EarningsResponse.model_validate(result)


@router.get("/{ticker}/technicals", response_model=TechnicalsResponse)
async def get_technicals(ticker: str, db: AsyncSession = Depends(get_db)) -> TechnicalsResponse:
    service = _get_service(db)
    result = await service.get_technicals(ticker)
    return TechnicalsResponse.model_validate(result)


@router.get("/{ticker}/news", response_model=NewsResponse)
async def get_news(
    ticker: str,
    limit: int = Query(10, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
) -> NewsResponse:
    service = _get_service(db)
    result = await service.get_news(ticker, limit)
    return NewsResponse.model_validate(result)


@router.get("/{ticker}/analyst", response_model=AnalystResponse)
async def get_analyst(ticker: str, db: AsyncSession = Depends(get_db)) -> AnalystResponse:
    service = _get_service(db)
    result = await service.get_analyst_insights(ticker)
    return AnalystResponse.model_validate(result)


@router.get("/{ticker}/executive-summary", response_model=ExecutiveSummaryResponse)
async def get_executive_summary(ticker: str, db: AsyncSession = Depends(get_db)) -> ExecutiveSummaryResponse:
    service = _get_service(db)
    result = await service.get_executive_summary(ticker)
    return ExecutiveSummaryResponse.model_validate(result)


@router.get("/{ticker}/videos", response_model=VideosResponse)
async def get_videos(ticker: str, db: AsyncSession = Depends(get_db)) -> VideosResponse:
    service = _get_service(db)
    result = await service.get_videos(ticker)
    return VideosResponse.model_validate(result)


@router.get("/{ticker}/intelligence", response_model=IntelligenceResponse)
async def get_intelligence(
    ticker: str,
    q: str | None = Query(None, description="Optional semantic search query scoped to this company's videos"),
    top_k: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> IntelligenceResponse:
    service = _get_service(db)
    result = await service.get_intelligence(ticker, semantic_query=q, top_k=top_k)
    return IntelligenceResponse.model_validate(result)


@router.post("/{ticker}/chat", response_model=ChatResponse)
async def chat(
    ticker: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    service = _get_service(db)
    result = await service.chat(ticker, question=body.question, top_k=body.top_k)
    return ChatResponse(
        answer=result.answer,
        citations=[
            ChatCitation(
                video_id=c.video_id,
                video_title=c.video_title,
                channel_name=c.channel_name,
                published_at=c.published_at,
                start_seconds=c.start_seconds,
            )
            for c in result.citations
        ],
        retrieved_chunks=result.retrieved_chunks,
        model_used=result.model_used,
    )
