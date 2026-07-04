"""Topic and VideoTopic junction model."""

from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    # Relationships
    video_topics: Mapped[list["VideoTopic"]] = relationship(
        "VideoTopic", back_populates="topic"
    )

    def __repr__(self) -> str:
        return f"<Topic id={self.id} name={self.name!r}>"


class VideoTopic(Base):
    __tablename__ = "video_topics"

    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True
    )
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True
    )

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="video_topics")  # noqa: F821
    topic: Mapped["Topic"] = relationship("Topic", back_populates="video_topics")

    def __repr__(self) -> str:
        return f"<VideoTopic video_id={self.video_id} topic_id={self.topic_id}>"
