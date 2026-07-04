"""Video ORM model."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    external_video_id: Mapped[str] = mapped_column(Text, nullable=False)
    video_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str] = mapped_column(Text, nullable=False, default="video")
    live_status: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Denormalized latest stats (fast reads)
    view_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    like_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Pipeline state machine
    pipeline_status: Mapped[str] = mapped_column(
        Text, nullable=False, default="DISCOVERED", server_default="DISCOVERED"
    )
    pipeline_failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    pipeline_retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    pipeline_next_retry_at: Mapped[datetime | None] = mapped_column(nullable=True, type_=None)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="videos")  # noqa: F821
    transcript: Mapped["Transcript | None"] = relationship(  # noqa: F821
        "Transcript", back_populates="video", uselist=False, cascade="all, delete-orphan"
    )
    summary: Mapped["Summary | None"] = relationship(  # noqa: F821
        "Summary", back_populates="video", uselist=False, cascade="all, delete-orphan"
    )
    investment_thesis: Mapped["InvestmentThesis | None"] = relationship(  # noqa: F821
        "InvestmentThesis", back_populates="video", uselist=False, cascade="all, delete-orphan"
    )
    sentiment: Mapped["Sentiment | None"] = relationship(  # noqa: F821
        "Sentiment", back_populates="video", uselist=False, cascade="all, delete-orphan"
    )
    quotes: Mapped[list["Quote"]] = relationship(  # noqa: F821
        "Quote", back_populates="video", cascade="all, delete-orphan"
    )
    key_numbers: Mapped[list["KeyNumber"]] = relationship(  # noqa: F821
        "KeyNumber", back_populates="video", cascade="all, delete-orphan"
    )
    actionable_insights: Mapped[list["ActionableInsight"]] = relationship(  # noqa: F821
        "ActionableInsight", back_populates="video", cascade="all, delete-orphan"
    )
    stat_snapshots: Mapped[list["VideoStatSnapshot"]] = relationship(  # noqa: F821
        "VideoStatSnapshot", back_populates="video", cascade="all, delete-orphan"
    )
    embeddings: Mapped[list["Embedding"]] = relationship(  # noqa: F821
        "Embedding", back_populates="video", cascade="all, delete-orphan"
    )
    video_companies: Mapped[list["VideoCompany"]] = relationship(  # noqa: F821
        "VideoCompany", back_populates="video", cascade="all, delete-orphan"
    )
    video_topics: Mapped[list["VideoTopic"]] = relationship(  # noqa: F821
        "VideoTopic", back_populates="video", cascade="all, delete-orphan"
    )
    ticker_sentiments: Mapped[list["VideoTickerSentiment"]] = relationship(  # noqa: F821
        "VideoTickerSentiment", back_populates="video", cascade="all, delete-orphan"
    )
    bookmarks: Mapped[list["Bookmark"]] = relationship(  # noqa: F821
        "Bookmark", back_populates="video", cascade="all, delete-orphan"
    )
    task_logs: Mapped[list["TaskLog"]] = relationship(  # noqa: F821
        "TaskLog", back_populates="video"
    )

    __table_args__ = (
        UniqueConstraint("channel_id", "external_video_id", name="uq_videos_channel_ext"),
        Index("idx_videos_pipeline_status", "pipeline_status"),
        Index("idx_videos_published_at", "published_at"),
        Index("idx_videos_channel", "channel_id"),
    )

    # Valid pipeline status values
    PIPELINE_STATUSES = frozenset({
        "DISCOVERED",
        "METADATA_SYNCED",
        "TRANSCRIPT_PENDING",
        "TRANSCRIPT_READY",
        "ANALYSIS_PENDING",
        "ANALYZED",
        "EMBEDDING_PENDING",
        "EMBEDDED",
        "INDEXED",
        "FAILED",
    })

    def __repr__(self) -> str:
        return (
            f"<Video id={self.id} ext={self.external_video_id!r} status={self.pipeline_status!r}>"
        )
