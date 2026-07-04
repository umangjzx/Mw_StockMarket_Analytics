"""
Financials ORM models — Company Intelligence Phase 2.

Additive only, same pattern as models/market_data.py: keyed off the existing
companies/tickers identity tables, no changes to the video-analysis schema.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Numeric, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FinancialStatement(Base):
    """One reporting period of one statement type (income/balance/cashflow),
    annual or quarterly. line_items is a curated subset, not the full ~40-70
    row dump yfinance returns — see yfinance_provider._CURATED_LINE_ITEMS."""

    __tablename__ = "financial_statements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    statement_type: Mapped[str] = mapped_column(Text, nullable=False)  # "income" | "balance" | "cashflow"
    period_type: Mapped[str] = mapped_column(Text, nullable=False)     # "annual" | "quarterly"
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    line_items: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)

    company: Mapped["Company"] = relationship("Company")  # noqa: F821

    __table_args__ = (
        UniqueConstraint(
            "company_id", "statement_type", "period_type", "period_end",
            name="uq_financial_statements_period",
        ),
        Index("idx_financial_statements_company", "company_id", "statement_type", "period_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<FinancialStatement company_id={self.company_id} "
            f"{self.statement_type}/{self.period_type} {self.period_end}>"
        )


class Ratios(Base):
    """1:1 latest ratio snapshot per ticker."""

    __tablename__ = "ratios"

    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), primary_key=True
    )
    pe_trailing: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pe_forward: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    peg_ratio: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    price_to_book: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    ev_to_ebitda: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    roe: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    roa: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    roic: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    debt_to_equity: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    current_ratio: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True)
    quick_ratio: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True)
    eps_trailing: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    eps_forward: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    beta: Mapped[Decimal | None] = mapped_column(Numeric(9, 4), nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)

    ticker: Mapped["Ticker"] = relationship("Ticker")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Ratios ticker_id={self.ticker_id} pe_trailing={self.pe_trailing}>"


class Earnings(Base):
    """1:1 latest earnings snapshot per company — next date/estimates plus a
    JSONB history of recent surprises, and an optional AI-generated summary
    (reuses the existing Ollama LLM provider, same as the video pipeline)."""

    __tablename__ = "earnings"

    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    next_earnings_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    eps_estimate_low: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    eps_estimate_avg: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    eps_estimate_high: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    revenue_estimate_low: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    revenue_estimate_avg: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    revenue_estimate_high: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(nullable=False)

    company: Mapped["Company"] = relationship("Company")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Earnings company_id={self.company_id} next={self.next_earnings_date}>"
