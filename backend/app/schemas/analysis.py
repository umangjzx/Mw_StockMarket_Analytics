"""Pydantic schemas for all analysis-related endpoints."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


# ── Summary ───────────────────────────────────────────────────────────────────

class SummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    video_id: int
    executive_bullets: list[str]
    detailed_summary: str
    model_used: str
    generated_at: datetime


# ── Investment thesis ─────────────────────────────────────────────────────────

class ThesisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    video_id: int
    bull_case: str | None
    bear_case: str | None
    risks: str | None
    catalysts: str | None
    valuation_discussion: str | None
    economic_outlook: str | None
    market_outlook: str | None
    generated_at: datetime


# ── Sentiment ─────────────────────────────────────────────────────────────────

class TickerSentimentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ticker: str
    sentiment: str
    confidence_score: Decimal | None

    @classmethod
    def from_orm_obj(cls, obj) -> "TickerSentimentItem":
        return cls(
            ticker=obj.ticker.symbol if obj.ticker else "UNKNOWN",
            sentiment=obj.sentiment,
            confidence_score=obj.confidence_score,
        )


class SentimentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    video_id: int
    overall_sentiment: str
    bullish_pct: Decimal
    bearish_pct: Decimal
    neutral_pct: Decimal
    confidence_score: Decimal
    generated_at: datetime
    ticker_sentiments: list[TickerSentimentItem] = []


# ── Quotes ────────────────────────────────────────────────────────────────────

class QuoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    video_id: int
    quote_text: str
    speaker: str | None
    start_seconds: Decimal | None
    importance_rank: int | None


class QuotesResponse(BaseModel):
    video_id: int
    quotes: list[QuoteResponse]


# ── Key numbers ───────────────────────────────────────────────────────────────

class KeyNumberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    video_id: int
    ticker: str | None
    metric_type: str
    value_text: str
    value_numeric: Decimal | None
    context: str | None
    start_seconds: Decimal | None

    @classmethod
    def from_orm_obj(cls, obj) -> "KeyNumberResponse":
        return cls(
            id=obj.id,
            video_id=obj.video_id,
            ticker=obj.ticker.symbol if obj.ticker else None,
            metric_type=obj.metric_type,
            value_text=obj.value_text,
            value_numeric=obj.value_numeric,
            context=obj.context,
            start_seconds=obj.start_seconds,
        )


class KeyNumbersResponse(BaseModel):
    video_id: int
    key_numbers: list[KeyNumberResponse]


# ── Actionable insights ───────────────────────────────────────────────────────

class InsightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    video_id: int
    insight_type: str
    ticker: str | None
    description: str
    event_date: date | None

    @classmethod
    def from_orm_obj(cls, obj) -> "InsightResponse":
        return cls(
            id=obj.id,
            video_id=obj.video_id,
            insight_type=obj.insight_type,
            ticker=obj.ticker.symbol if obj.ticker else None,
            description=obj.description,
            event_date=obj.event_date,
        )


class InsightsResponse(BaseModel):
    video_id: int
    insights: list[InsightResponse]


# ── Companies ─────────────────────────────────────────────────────────────────

class TickerItem(BaseModel):
    id: int
    symbol: str
    exchange: str | None


class CompanyItem(BaseModel):
    id: int
    name: str
    sector: str | None
    tickers: list[TickerItem]
    mention_count: int


class CompaniesResponse(BaseModel):
    video_id: int
    companies: list[CompanyItem]
