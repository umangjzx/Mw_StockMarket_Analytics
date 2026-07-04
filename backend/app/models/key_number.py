"""KeyNumber ORM model — extracted financial figures."""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class KeyNumber(Base):
    __tablename__ = "key_numbers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    ticker_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("tickers.id", ondelete="SET NULL"), nullable=True
    )
    metric_type: Mapped[str] = mapped_column(Text, nullable=False)
    value_text: Mapped[str] = mapped_column(Text, nullable=False)
    value_numeric: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_seconds: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="key_numbers")  # noqa: F821
    ticker: Mapped["Ticker | None"] = relationship("Ticker", back_populates="key_numbers")  # noqa: F821

    __table_args__ = (
        Index("idx_key_numbers_video", "video_id"),
        Index("idx_key_numbers_ticker", "ticker_id"),
    )

    def __repr__(self) -> str:
        return f"<KeyNumber id={self.id} video_id={self.video_id} metric={self.metric_type!r} value={self.value_text!r}>"
