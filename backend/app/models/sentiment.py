"""Sentiment ORM models — overall and per-ticker."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Sentiment(Base):
    __tablename__ = "sentiments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    overall_sentiment: Mapped[str] = mapped_column(Text, nullable=False)
    bullish_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    bearish_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    neutral_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="sentiment")  # noqa: F821

    __table_args__ = (
        CheckConstraint(
            "(bullish_pct + bearish_pct + neutral_pct) BETWEEN 99 AND 101",
            name="ck_sentiments_pct_sum",
        ),
    )

    def __repr__(self) -> str:
        return f"<Sentiment id={self.id} video_id={self.video_id} overall={self.overall_sentiment!r}>"


class VideoTickerSentiment(Base):
    __tablename__ = "video_ticker_sentiments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    ticker_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False
    )
    sentiment: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="ticker_sentiments")  # noqa: F821
    ticker: Mapped["Ticker"] = relationship("Ticker", back_populates="ticker_sentiments")  # noqa: F821

    __table_args__ = (
        UniqueConstraint("video_id", "ticker_id", name="uq_video_ticker_sentiments"),
    )

    def __repr__(self) -> str:
        return f"<VideoTickerSentiment id={self.id} video_id={self.video_id} ticker_id={self.ticker_id} sentiment={self.sentiment!r}>"
