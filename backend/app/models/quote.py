"""Quote ORM model — notable quotes extracted from transcripts."""

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, SmallInteger, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Quote(Base):
    __tablename__ = "quotes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    # Optional FK to the segment for timestamp lookup — nullable since we also store start_seconds
    segment_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("transcript_segments.id", ondelete="SET NULL"), nullable=True
    )
    quote_text: Mapped[str] = mapped_column(Text, nullable=False)
    speaker: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_seconds: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    importance_rank: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="quotes")  # noqa: F821
    segment: Mapped["TranscriptSegment | None"] = relationship(  # noqa: F821
        "TranscriptSegment", back_populates="quotes", foreign_keys=[segment_id]
    )

    __table_args__ = (
        UniqueConstraint("video_id", "importance_rank", name="uq_quotes_video_rank"),
    )

    def __repr__(self) -> str:
        return f"<Quote id={self.id} video_id={self.video_id} rank={self.importance_rank}>"
