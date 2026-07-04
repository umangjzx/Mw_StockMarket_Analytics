"""Company, Ticker, and junction models."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    sector: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    # Relationships
    tickers: Mapped[list["Ticker"]] = relationship(
        "Ticker", back_populates="company"
    )
    video_companies: Mapped[list["VideoCompany"]] = relationship(
        "VideoCompany", back_populates="company"
    )

    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name!r}>"


class Ticker(Base):
    __tablename__ = "tickers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    company_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    exchange: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    company: Mapped["Company | None"] = relationship("Company", back_populates="tickers")
    key_numbers: Mapped[list["KeyNumber"]] = relationship(  # noqa: F821
        "KeyNumber", back_populates="ticker"
    )
    actionable_insights: Mapped[list["ActionableInsight"]] = relationship(  # noqa: F821
        "ActionableInsight", back_populates="ticker"
    )
    ticker_sentiments: Mapped[list["VideoTickerSentiment"]] = relationship(  # noqa: F821
        "VideoTickerSentiment", back_populates="ticker"
    )
    watchlist_items: Mapped[list["WatchlistItem"]] = relationship(  # noqa: F821
        "WatchlistItem", back_populates="ticker"
    )

    __table_args__ = (
        UniqueConstraint("symbol", "exchange", name="uq_tickers_symbol_exchange"),
    )

    def __repr__(self) -> str:
        return f"<Ticker id={self.id} symbol={self.symbol!r} exchange={self.exchange!r}>"


class VideoCompany(Base):
    __tablename__ = "video_companies"

    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="video_companies")  # noqa: F821
    company: Mapped["Company"] = relationship("Company", back_populates="video_companies")

    def __repr__(self) -> str:
        return f"<VideoCompany video_id={self.video_id} company_id={self.company_id} count={self.mention_count}>"
