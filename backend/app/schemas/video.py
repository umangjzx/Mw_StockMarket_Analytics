"""Pydantic schemas for Video endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


# ── Response schemas ──────────────────────────────────────────────────────────

class VideoResponse(BaseModel):
    """Video detail response — metadata + latest stats."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    channel_id: int
    external_video_id: str
    video_url: str
    title: str
    description: str | None
    thumbnail_url: str | None
    published_at: datetime
    duration_seconds: int | None
    language: str | None
    tags: list[str] | None
    category: str | None
    content_type: str
    live_status: str | None
    view_count: int | None
    like_count: int | None
    comment_count: int | None
    pipeline_status: str
    pipeline_failure_reason: str | None
    pipeline_retry_count: int
    created_at: datetime
    updated_at: datetime


class VideoListResponse(BaseModel):
    """Paginated video list response."""
    items: list[VideoResponse]
    page: int
    page_size: int
    total: int


class PipelineStatusCount(BaseModel):
    """Count of videos per pipeline status, for admin dashboard."""
    status: str
    count: int


class PipelineStatusSummary(BaseModel):
    """Summary of pipeline status across all videos."""
    counts: list[PipelineStatusCount]
    total: int
