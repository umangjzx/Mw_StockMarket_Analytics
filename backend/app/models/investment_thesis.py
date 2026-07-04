"""InvestmentThesis ORM model."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class InvestmentThesis(Base):
    __tablename__ = "investment_theses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    bull_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    bear_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    risks: Mapped[str | None] = mapped_column(Text, nullable=True)
    catalysts: Mapped[str | None] = mapped_column(Text, nullable=True)
    valuation_discussion: Mapped[str | None] = mapped_column(Text, nullable=True)
    economic_outlook: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_outlook: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="investment_thesis")  # noqa: F821

    def __repr__(self) -> str:
        return f"<InvestmentThesis id={self.id} video_id={self.video_id}>"
