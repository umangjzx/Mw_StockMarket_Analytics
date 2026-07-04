"""Embedding ORM model — pgvector embeddings of transcript segments."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.db.base import Base


class Embedding(Base):
    __tablename__ = "embeddings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    transcript_segment_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("transcript_segments.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Denormalized for fast filtering
    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    # text-embedding-3-small = 1536 dims, nomic-embed-text = 768 dims
    # Dimension is configurable via EMBEDDING_DIMENSIONS env var (default 768 for Ollama)
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)
    model_used: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    # Relationships
    segment: Mapped["TranscriptSegment"] = relationship(  # noqa: F821
        "TranscriptSegment", back_populates="embeddings"
    )
    video: Mapped["Video"] = relationship("Video", back_populates="embeddings")  # noqa: F821

    __table_args__ = (
        # HNSW index for cosine similarity search (pgvector)
        Index("idx_embeddings_hnsw", "embedding", postgresql_using="hnsw", postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("idx_embeddings_video", "video_id"),
    )

    def __repr__(self) -> str:
        return f"<Embedding id={self.id} segment_id={self.transcript_segment_id} video_id={self.video_id}>"
