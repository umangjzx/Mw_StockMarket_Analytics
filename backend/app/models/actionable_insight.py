"""ActionableInsight ORM model."""

from datetime import date

from sqlalchemy import BigInteger, Date, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ActionableInsight(Base):
    __tablename__ = "actionable_insights"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    ticker_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="SET NULL"), nullable=True
    )
    insight_type: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="actionable_insights")  # noqa: F821
    ticker: Mapped["Ticker | None"] = relationship("Ticker", back_populates="actionable_insights")  # noqa: F821

    __table_args__ = (
        Index("idx_insights_type", "insight_type"),
    )

    def __repr__(self) -> str:
        return f"<ActionableInsight id={self.id} video_id={self.video_id} type={self.insight_type!r}>"
