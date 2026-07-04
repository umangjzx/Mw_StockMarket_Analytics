"""Pydantic schemas for the Company Intelligence module (Phase 1)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

# "live" = just fetched from the provider, "cached" = served from Redis/Postgres
# within its freshness window, "unavailable" = the graceful-fallback case —
# every field-group below carries its own status rather than a bare null.
DataStatus = str


class TickerIdentity(BaseModel):
    ticker_id: int | None
    symbol: str
    exchange: str | None
    company_id: int | None
    company_name: str | None
    sector: str | None
    industry: str | None


class ResolveResponse(BaseModel):
    query: str
    candidates: list[TickerIdentity]


# ── Section 1: Live market data ─────────────────────────────────────────────

class QuoteData(BaseModel):
    price: float | None = None
    change_abs: float | None = None
    change_pct: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    volume: int | None = None
    market_cap: float | None = None
    week52_high: float | None = None
    week52_low: float | None = None
    bid: float | None = None
    ask: float | None = None
    vwap: float | None = None
    pre_market_price: float | None = None
    after_hours_price: float | None = None
    currency: str | None = None
    source: str | None = None
    fetched_at: str | None = None
    status: DataStatus


class QuoteResponse(BaseModel):
    ticker: TickerIdentity
    quote: QuoteData


# ── Section 2: Interactive charts ───────────────────────────────────────────

class ChartBar(BaseModel):
    ts: str
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None


class ChartResponse(BaseModel):
    ticker: TickerIdentity
    range: str
    bars: list[ChartBar]
    status: DataStatus


# ── Section 3: Company overview ─────────────────────────────────────────────

class ProfileData(BaseModel):
    description: str | None = None
    ceo: str | None = None
    headquarters: str | None = None
    employees: int | None = None
    website: str | None = None
    primary_exchange: str | None = None
    ipo_date: str | None = None
    business_segments: list[str] = []
    source: str | None = None
    source_url: str | None = None
    fetched_at: str | None = None
    status: DataStatus


class ProfileResponse(BaseModel):
    ticker: TickerIdentity
    profile: ProfileData


# ── Section 5: Key financial ratios ─────────────────────────────────────────

class RatiosData(BaseModel):
    pe_trailing: float | None = None
    pe_forward: float | None = None
    peg_ratio: float | None = None
    price_to_book: float | None = None
    ev_to_ebitda: float | None = None
    roe: float | None = None
    roa: float | None = None
    roic: float | None = None
    debt_to_equity: float | None = None
    dividend_yield: float | None = None
    current_ratio: float | None = None
    quick_ratio: float | None = None
    eps_trailing: float | None = None
    eps_forward: float | None = None
    beta: float | None = None
    source: str | None = None
    fetched_at: str | None = None
    status: DataStatus


class RatiosResponse(BaseModel):
    ticker: TickerIdentity
    ratios: RatiosData


# ── Section 4: Financial statements ─────────────────────────────────────────

class FinancialPeriodItem(BaseModel):
    period_end: str
    line_items: dict[str, float | None]


class FinancialsResponse(BaseModel):
    ticker: TickerIdentity
    statement_type: str
    period_type: str
    periods: list[FinancialPeriodItem]
    status: DataStatus


# ── Section 6: Earnings ──────────────────────────────────────────────────────

class EarningsHistoryItem(BaseModel):
    earnings_date: str
    eps_estimate: float | None
    eps_reported: float | None
    surprise_pct: float | None


class EarningsData(BaseModel):
    next_earnings_date: str | None = None
    eps_estimate_low: float | None = None
    eps_estimate_avg: float | None = None
    eps_estimate_high: float | None = None
    revenue_estimate_low: float | None = None
    revenue_estimate_avg: float | None = None
    revenue_estimate_high: float | None = None
    history: list[EarningsHistoryItem] = []
    ai_summary: str | None = None
    source: str | None = None
    fetched_at: str | None = None
    status: DataStatus


class EarningsResponse(BaseModel):
    ticker: TickerIdentity
    earnings: EarningsData


# ── Section 11: Technical analysis ──────────────────────────────────────────

class SmaBlock(BaseModel):
    sma_20: float | None = None
    sma_50: float | None = None
    sma_200: float | None = None


class EmaBlock(BaseModel):
    ema_12: float | None = None
    ema_26: float | None = None


class MacdBlock(BaseModel):
    macd_line: float | None
    signal_line: float | None
    histogram: float | None


class BollingerBandsBlock(BaseModel):
    upper: float | None
    middle: float | None
    lower: float | None


class SupportResistanceBlock(BaseModel):
    resistance_20d: float | None = None
    support_20d: float | None = None
    resistance_60d: float | None = None
    support_60d: float | None = None


class TechnicalsData(BaseModel):
    as_of: str | None = None
    bars_used: int | None = None
    sma: SmaBlock | None = None
    ema: EmaBlock | None = None
    rsi_14: float | None = None
    macd: MacdBlock | None = None
    bollinger_bands: BollingerBandsBlock | None = None
    atr_14: float | None = None
    stochastic_rsi_14: float | None = None
    support_resistance: SupportResistanceBlock | None = None
    trend: str | None = None
    status: DataStatus
    reason: str | None = None


class TechnicalsResponse(BaseModel):
    ticker: TickerIdentity
    technicals: TechnicalsData


# ── Section 7: News aggregation ──────────────────────────────────────────────

class NewsArticleItem(BaseModel):
    title: str
    summary: str
    source: str
    url: str
    published_at: str
    thumbnail_url: str | None = None
    sentiment: str | None = None
    impact_score: float | None = None
    related_tickers: list[str] = []


class NewsData(BaseModel):
    articles: list[NewsArticleItem] = []
    status: DataStatus


class NewsResponse(BaseModel):
    ticker: TickerIdentity
    news: NewsData


# ── Section 9: Analyst insights ──────────────────────────────────────────────

class RecommendationPeriodItem(BaseModel):
    period: str
    strong_buy: int
    buy: int
    hold: int
    sell: int
    strong_sell: int


class AnalystActionItem(BaseModel):
    grade_date: str
    firm: str
    to_grade: str
    from_grade: str
    action: str
    current_price_target: float | None = None
    prior_price_target: float | None = None


class InstitutionalHolderItem(BaseModel):
    holder: str
    shares: int
    date_reported: str | None = None
    pct_held: float | None = None
    value: float | None = None
    pct_change: float | None = None


class InsiderTransactionItem(BaseModel):
    insider: str
    position: str | None = None
    text: str | None = None
    shares: int | None = None
    value: float | None = None
    start_date: str | None = None
    ownership: str | None = None


class AnalystData(BaseModel):
    recommendation_mean: float | None = None
    recommendation_key: str | None = None
    target_mean: float | None = None
    target_high: float | None = None
    target_low: float | None = None
    target_median: float | None = None
    num_analyst_opinions: int | None = None
    held_pct_institutions: float | None = None
    held_pct_insiders: float | None = None
    recommendation_trend: list[RecommendationPeriodItem] = []
    actions: list[AnalystActionItem] = []
    institutional_holders: list[InstitutionalHolderItem] = []
    insider_transactions: list[InsiderTransactionItem] = []
    source: str | None = None
    fetched_at: str | None = None
    status: DataStatus


class AnalystResponse(BaseModel):
    ticker: TickerIdentity
    analyst: AnalystData


# ── Section 14: AI executive summary ─────────────────────────────────────────

class ExecutiveSummaryData(BaseModel):
    business_overview: str | None = None
    market_outlook: str | None = None
    why_moving_today: str | None = None
    positive_factors: list[str] = []
    risks: list[str] = []
    opportunities: list[str] = []
    financial_health: str | None = None
    technical_outlook: str | None = None
    news_summary: str | None = None
    overall_sentiment: str | None = None
    investment_thesis: str | None = None
    short_term_outlook: str | None = None
    long_term_outlook: str | None = None
    confidence_score: float | None = None
    source: str | None = None
    fetched_at: str | None = None
    status: DataStatus


class ExecutiveSummaryResponse(BaseModel):
    ticker: TickerIdentity
    executive_summary: ExecutiveSummaryData


# ── Overview (main entry-point page) ────────────────────────────────────────

class OverviewResponse(BaseModel):
    ticker: TickerIdentity
    quote: QuoteData
    profile: ProfileData
    video_mention_count: int


# ── Section 10: AI Video Intelligence (reused from the existing pipeline) ──

class VideoSummaryItem(BaseModel):
    id: int
    title: str
    external_video_id: str
    video_url: str
    published_at: datetime | None
    channel_name: str | None
    pipeline_status: str


class VideosResponse(BaseModel):
    ticker: TickerIdentity
    videos: list[VideoSummaryItem]


class SummaryBlock(BaseModel):
    executive_bullets: list[str]
    detailed_summary: str
    model_used: str
    generated_at: datetime


class ThesisBlock(BaseModel):
    bull_case: str | None
    bear_case: str | None
    risks: str | None
    catalysts: str | None
    valuation_discussion: str | None
    economic_outlook: str | None
    market_outlook: str | None


class SentimentBlock(BaseModel):
    overall_sentiment: str
    bullish_pct: Decimal
    bearish_pct: Decimal
    neutral_pct: Decimal
    confidence_score: Decimal


class KeyNumberBlock(BaseModel):
    metric_type: str
    value_text: str
    value_numeric: Decimal | None
    context: str | None


class QuoteBlock(BaseModel):
    quote_text: str
    speaker: str | None
    start_seconds: Decimal | None
    importance_rank: int | None


class InsightBlock(BaseModel):
    insight_type: str
    description: str
    event_date: date | None


class VideoIntelligenceBundle(BaseModel):
    video: VideoSummaryItem
    summary: SummaryBlock | None
    thesis: ThesisBlock | None
    sentiment: SentimentBlock | None
    key_numbers: list[KeyNumberBlock]
    quotes: list[QuoteBlock]
    insights: list[InsightBlock]


class SemanticResultItem(BaseModel):
    video_id: int
    video_title: str
    segment_id: int
    text: str
    start_seconds: Decimal | None
    end_seconds: Decimal | None
    similarity: float


class IntelligenceResponse(BaseModel):
    ticker: TickerIdentity
    videos: list[VideoIntelligenceBundle]
    semantic_query: str | None
    semantic_results: list[SemanticResultItem]


class ChatRequest(BaseModel):
    question: str
    top_k: int = 10


class ChatCitation(BaseModel):
    video_id: int
    video_title: str
    channel_name: str
    published_at: datetime | None
    start_seconds: float | None


class ChatResponse(BaseModel):
    answer: str
    citations: list[ChatCitation]
    retrieved_chunks: int
    model_used: str
