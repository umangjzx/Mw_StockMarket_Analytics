"""Pydantic schemas for reports and analytics."""

from datetime import date, datetime
from pydantic import BaseModel, ConfigDict


class DailyReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    report_date: date
    market_summary: str | None
    most_mentioned_stocks: list | dict | None
    trending_sectors: list | dict | None
    most_bullish_stocks: list | dict | None
    most_bearish_stocks: list | dict | None
    most_discussed_companies: list | dict | None
    analyst_consensus: str | None
    conflicting_opinions: str | None
    interesting_insights: str | None
    generated_at: datetime


class TrendingTickerItem(BaseModel):
    ticker: str
    mentions: int
    window: str


class SentimentTimeSeriesPoint(BaseModel):
    date: date
    bullish_pct: float
    bearish_pct: float
    neutral_pct: float
    video_count: int


class CreatorStatsResponse(BaseModel):
    channel_id: int
    video_count: int
    avg_bullish_pct: float
    avg_bearish_pct: float
    top_tickers: list[str]
