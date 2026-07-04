"""
Market data ORM models — Company Intelligence Phase 1.

Additive only: these tables carry externally-sourced market data keyed off
the existing companies/tickers identity tables. Nothing here touches the
video-analysis pipeline's schema.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CompanyProfile(Base):
    """1:1 company overview/fundamentals metadata, sourced from a market data provider."""

    __tablename__ = "company_profiles"

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ceo: Mapped[str | None] = mapped_column(Text, nullable=True)
    headquarters: Mapped[str | None] = mapped_column(Text, nullable=True)
    employees: Mapped[int | None] = mapped_column(Integer, nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_exchange: Mapped[str | None] = mapped_column(Text, nullable=True)
    ipo_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    business_segments: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)

    company: Mapped["Company"] = relationship("Company")  # noqa: F821

    def __repr__(self) -> str:
        return f"<CompanyProfile company_id={self.company_id} source={self.source!r}>"


class MarketQuote(Base):
    """1:1 latest quote snapshot per ticker — upserted on every refresh."""

    __tablename__ = "market_quotes"

    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), primary_key=True
    )
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    change_abs: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    change_pct: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True)
    open: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    high: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    low: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    prev_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(24, 2), nullable=True)
    week52_high: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    week52_low: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    bid: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    ask: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    vwap: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    pre_market_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    after_hours_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)

    ticker: Mapped["Ticker"] = relationship("Ticker")  # noqa: F821

    def __repr__(self) -> str:
        return f"<MarketQuote ticker_id={self.ticker_id} price={self.price} source={self.source!r}>"


class PriceBar(Base):
    """Historical OHLCV bar for charting. Daily+ intervals are persisted; intraday is cache-only."""

    __tablename__ = "price_bars"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False
    )
    interval: Mapped[str] = mapped_column(Text, nullable=False)  # "1d", "1wk", "1mo"
    ts: Mapped[datetime] = mapped_column(nullable=False)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    ticker: Mapped["Ticker"] = relationship("Ticker")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("ticker_id", "interval", "ts", name="uq_price_bars_ticker_interval_ts"),
        Index("idx_price_bars_ticker_interval", "ticker_id", "interval"),
    )

    def __repr__(self) -> str:
        return f"<PriceBar ticker_id={self.ticker_id} interval={self.interval!r} ts={self.ts}>"
