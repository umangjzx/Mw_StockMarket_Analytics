"""Pydantic schemas for search and chat endpoints."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ── Structured search ─────────────────────────────────────────────────────────

class VideoSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    external_video_id: str
    video_url: str
    title: str
    thumbnail_url: str | None
    published_at: datetime
    duration_seconds: int | None
    content_type: str
    pipeline_status: str
    channel_id: int
    view_count: int | None


class StructuredSearchResponse(BaseModel):
    items: list[VideoSearchResult]
    page: int
    page_size: int
    total: int


# ── Semantic search ───────────────────────────────────────────────────────────

class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)
    top_k: int = Field(10, ge=1, le=50)
    filters: dict = Field(default_factory=dict, description="Optional filters: channel_id, date_from, date_to, video_id")


class SemanticChunkResult(BaseModel):
    video_id: int
    video_title: str
    external_video_id: str
    published_at: datetime | None
    channel_id: int
    segment_id: int
    text: str
    start_seconds: Decimal | None
    end_seconds: Decimal | None
    similarity: float


class SemanticSearchResponse(BaseModel):
    query: str
    results: list[SemanticChunkResult]
    total: int


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatSessionCreate(BaseModel):
    ticker: str | None = None
    watchlist_id: int | None = None
    channel_id: int | None = None


class ChatSessionResponse(BaseModel):
    id: str
    created_at: datetime
    ticker: str | None = None
    channel_id: int | None = None


class ChatMessageRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    top_k: int = Field(10, ge=1, le=50)


class CitationResponse(BaseModel):
    video_id: int
    video_title: str
    channel_name: str
    published_at: datetime | None
    start_seconds: float | None


class ChatMessageResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    citations: list[CitationResponse]
    retrieved_chunks: int
    model_used: str
