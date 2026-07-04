"""DailyReport and ReportVideoLink ORM models."""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, SmallInteger, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    market_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    most_mentioned_stocks: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    trending_sectors: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    most_bullish_stocks: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    most_bearish_stocks: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    most_discussed_companies: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    analyst_consensus: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflicting_opinions: Mapped[str | None] = mapped_column(Text, nullable=True)
    interesting_insights: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    # Relationships
    video_links: Mapped[list["ReportVideoLink"]] = relationship(
        "ReportVideoLink", back_populates="report", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<DailyReport id={self.id} date={self.report_date}>"


class ReportVideoLink(Base):
    __tablename__ = "report_video_links"

    report_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("daily_reports.id", ondelete="CASCADE"), primary_key=True
    )
    video_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True
    )
    link_type: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    rank: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Relationships
    report: Mapped["DailyReport"] = relationship("DailyReport", back_populates="video_links")

    def __repr__(self) -> str:
        return f"<ReportVideoLink report_id={self.report_id} video_id={self.video_id} type={self.link_type!r}>"
