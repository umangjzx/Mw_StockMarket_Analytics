"""Pydantic schemas for Channel endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Request schemas ────────────────────────────────────────────────────────────

class ChannelCreate(BaseModel):
    """Body for POST /channels — add a new channel."""
    platform: Literal["youtube"] = "youtube"
    # Either external_channel_id (UCxxx) or handle (@CNBC)
    external_channel_id: str | None = Field(None, description="YouTube channel ID (UC...)")
    handle: str | None = Field(None, description="YouTube handle e.g. @CNBC")
    polling_interval_seconds: int = Field(900, ge=60, le=86400, description="How often to poll (seconds)")
    include_shorts: bool = False

    def channel_identifier(self) -> str:
        """Return whichever identifier was provided."""
        if self.external_channel_id:
            return self.external_channel_id
        if self.handle:
            return self.handle
        raise ValueError("Either external_channel_id or handle must be provided")


class ChannelUpdate(BaseModel):
    """Body for PATCH /channels/{id}."""
    is_active: bool | None = None
    polling_interval_seconds: int | None = Field(None, ge=60, le=86400)
    include_shorts: bool | None = None


# ── Response schemas ──────────────────────────────────────────────────────────

class ChannelResponse(BaseModel):
    """Channel detail response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    external_channel_id: str
    handle: str | None
    display_name: str
    description: str | None
    thumbnail_url: str | None
    country: str | None
    subscriber_count: int | None
    is_active: bool
    include_shorts: bool
    polling_interval_seconds: int
    last_polled_at: datetime | None
    last_successful_poll_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ChannelListResponse(BaseModel):
    """Paginated channel list response."""
    items: list[ChannelResponse]
    page: int
    page_size: int
    total: int
