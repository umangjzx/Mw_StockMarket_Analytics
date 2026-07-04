"""Transcript ORM models — full text and timestamped segments."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="transcript")  # noqa: F821
    segments: Mapped[list["TranscriptSegment"]] = relationship(
        "TranscriptSegment", back_populates="transcript", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Transcript id={self.id} video_id={self.video_id} source={self.source!r}>"


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    transcript_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("transcripts.id", ondelete="CASCADE"), nullable=False
    )
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    start_seconds: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    end_seconds: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    transcript: Mapped["Transcript"] = relationship("Transcript", back_populates="segments")
    embeddings: Mapped[list["Embedding"]] = relationship(  # noqa: F821
        "Embedding", back_populates="segment", cascade="all, delete-orphan"
    )
    quotes: Mapped[list["Quote"]] = relationship(  # noqa: F821
        "Quote", back_populates="segment", foreign_keys="[Quote.segment_id]"
    )

    __table_args__ = (
        UniqueConstraint("transcript_id", "sequence_no", name="uq_segments_transcript_seq"),
        Index("idx_segments_transcript", "transcript_id"),
    )

    def __repr__(self) -> str:
        return f"<TranscriptSegment id={self.id} transcript_id={self.transcript_id} seq={self.sequence_no}>"
