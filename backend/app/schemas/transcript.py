"""Pydantic schemas for Transcript endpoints."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TranscriptSegmentResponse(BaseModel):
    """A single timestamped segment."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    sequence_no: int
    start_seconds: Decimal
    end_seconds: Decimal
    text: str


class TranscriptResponse(BaseModel):
    """Full transcript with metadata. Segments are paginated separately."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    source: str
    language: str | None
    full_text: str
    word_count: int | None
    generated_at: datetime


class TranscriptSegmentListResponse(BaseModel):
    """Paginated segment list (returned from GET /videos/{id}/transcript?segments=true)."""
    transcript: TranscriptResponse
    segments: list[TranscriptSegmentResponse]
    page: int
    page_size: int
    total_segments: int
