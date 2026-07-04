"""Summary ORM model — executive bullets and detailed summary."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # JSONB array of bullet strings: ["...", "...", ...]
    executive_bullets: Mapped[dict | list] = mapped_column(JSONB, nullable=False)
    detailed_summary: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="summary")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Summary id={self.id} video_id={self.video_id}>"
