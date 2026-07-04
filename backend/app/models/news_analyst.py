"""
News, analyst insights, and AI executive summary ORM models — Company
Intelligence Phase 3. Additive only, same pattern as market_data.py and
financials.py.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class NewsArticle(Base):
    """A news article for a company. sentiment/impact_score/related_tickers
    are filled in by news_service's AI classification pass, not the raw
    provider fetch — they start NULL until that pass runs."""

    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    related_tickers: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)

    company: Mapped["Company"] = relationship("Company")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("company_id", "url", name="uq_news_articles_company_url"),
        Index("idx_news_articles_company_published", "company_id", "published_at"),
    )

    def __repr__(self) -> str:
        return f"<NewsArticle company_id={self.company_id} title={self.title[:40]!r}>"


class AnalystSnapshot(Base):
    """1:1 latest analyst-insights snapshot per ticker."""

    __tablename__ = "analyst_snapshots"

    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), primary_key=True
    )
    recommendation_mean: Mapped[Decimal | None] = mapped_column(Numeric(5, 3), nullable=True)
    recommendation_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_mean: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    target_high: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    target_low: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    target_median: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    num_analyst_opinions: Mapped[int | None] = mapped_column(nullable=True)
    held_pct_institutions: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    held_pct_insiders: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    recommendation_trend: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    actions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    institutional_holders: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    insider_transactions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)

    ticker: Mapped["Ticker"] = relationship("Ticker")  # noqa: F821

    def __repr__(self) -> str:
        return f"<AnalystSnapshot ticker_id={self.ticker_id} recommendation={self.recommendation_key!r}>"


class ExecutiveSummary(Base):
    """1:1 latest AI-synthesized executive summary per ticker — the capstone
    view that stitches together quote, ratios, technicals, earnings, news,
    analyst data, and the existing AI video intelligence into one narrative."""

    __tablename__ = "executive_summaries"

    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), primary_key=True
    )
    business_overview: Mapped[str] = mapped_column(Text, nullable=False)
    market_outlook: Mapped[str] = mapped_column(Text, nullable=False)
    why_moving_today: Mapped[str] = mapped_column(Text, nullable=False)
    positive_factors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    risks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    opportunities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    financial_health: Mapped[str] = mapped_column(Text, nullable=False)
    technical_outlook: Mapped[str] = mapped_column(Text, nullable=False)
    news_summary: Mapped[str] = mapped_column(Text, nullable=False)
    overall_sentiment: Mapped[str] = mapped_column(Text, nullable=False)
    investment_thesis: Mapped[str] = mapped_column(Text, nullable=False)
    short_term_outlook: Mapped[str] = mapped_column(Text, nullable=False)
    long_term_outlook: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)

    ticker: Mapped["Ticker"] = relationship("Ticker")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ExecutiveSummary ticker_id={self.ticker_id} sentiment={self.overall_sentiment!r}>"
