"""VideoStatSnapshot ORM model — historical engagement metric snapshots."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class VideoStatSnapshot(Base):
    __tablename__ = "video_stat_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    captured_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    view_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    like_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="stat_snapshots")  # noqa: F821

    __table_args__ = (
        Index("idx_stat_snapshots_video", "video_id", "captured_at"),
    )

    def __repr__(self) -> str:
        return f"<VideoStatSnapshot id={self.id} video_id={self.video_id} at={self.captured_at}>"
