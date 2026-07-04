"""Channel management endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import require_admin_key
from app.db.session import get_db
from app.providers.video_platforms.youtube_provider import YouTubeProvider
from app.repositories.channel_repository import ChannelRepository
from app.repositories.video_repository import VideoRepository
from app.schemas.channel import (
    ChannelCreate,
    ChannelListResponse,
    ChannelResponse,
    ChannelUpdate,
)
from app.schemas.video import VideoResponse
from app.services.channel_discovery_service import ChannelDiscoveryService
from app.services.quota_tracker import QuotaTracker
from app.workers.tasks.discovery_tasks import poll_channel as poll_channel_task

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=ChannelListResponse)
async def list_channels(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> ChannelListResponse:
    """List all configured channels with pagination."""
    repo = ChannelRepository(db)
    items, total = await repo.list_paginated(page=page, page_size=page_size, active_only=active_only)
    return ChannelListResponse(items=items, page=page, page_size=page_size, total=total)


@router.post("", response_model=ChannelResponse, dependencies=[Depends(require_admin_key)])
async def add_channel(
    data: ChannelCreate,
    db: AsyncSession = Depends(get_db),
) -> ChannelResponse:
    """Add a new channel (admin-only). Resolves the handle/ID, fetches metadata, and persists."""
    provider = YouTubeProvider()
    quota = QuotaTracker()
    service = ChannelDiscoveryService(db, provider, quota)
    channel = await service.add_channel(
        channel_id_or_handle=data.channel_identifier(),
        platform=data.platform,
        polling_interval_seconds=data.polling_interval_seconds,
        include_shorts=data.include_shorts,
    )
    return ChannelResponse.model_validate(channel)


@router.get("/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
) -> ChannelResponse:
    """Get channel details."""
    repo = ChannelRepository(db)
    channel = await repo.get_by_id(channel_id)
    if not channel:
        raise NotFoundError(f"Channel {channel_id} not found")
    return ChannelResponse.model_validate(channel)


@router.patch("/{channel_id}", response_model=ChannelResponse, dependencies=[Depends(require_admin_key)])
async def update_channel(
    channel_id: int,
    data: ChannelUpdate,
    db: AsyncSession = Depends(get_db),
) -> ChannelResponse:
    """Update channel config (admin-only)."""
    repo = ChannelRepository(db)
    channel = await repo.get_by_id(channel_id)
    if not channel:
        raise NotFoundError(f"Channel {channel_id} not found")
    if data.is_active is not None:
        channel.is_active = data.is_active
    if data.polling_interval_seconds is not None:
        channel.polling_interval_seconds = data.polling_interval_seconds
    if data.include_shorts is not None:
        channel.include_shorts = data.include_shorts
    await db.flush()
    await db.refresh(channel)
    return ChannelResponse.model_validate(channel)


@router.delete("/{channel_id}", status_code=204, dependencies=[Depends(require_admin_key)])
async def deactivate_channel(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Deactivate a channel (soft-delete via is_active=false). Videos are retained."""
    repo = ChannelRepository(db)
    channel = await repo.get_by_id(channel_id)
    if not channel:
        raise NotFoundError(f"Channel {channel_id} not found")
    channel.is_active = False
    await db.flush()


@router.get("/{channel_id}/videos")
async def list_channel_videos(
    channel_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Videos from this channel (paginated)."""
    repo = ChannelRepository(db)
    channel = await repo.get_by_id(channel_id)
    if not channel:
        raise NotFoundError(f"Channel {channel_id} not found")
    video_repo = VideoRepository(db)
    items, total = await video_repo.list_paginated(
        page=page, page_size=page_size, channel_id=channel_id
    )
    return {
        "items": [VideoResponse.model_validate(v) for v in items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


@router.post("/{channel_id}/poll-now", dependencies=[Depends(require_admin_key)])
async def poll_channel_now(
    channel_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger an immediate poll for this channel (admin-only, async via Celery)."""
    repo = ChannelRepository(db)
    channel = await repo.get_by_id(channel_id)
    if not channel:
        raise NotFoundError(f"Channel {channel_id} not found")
    task = poll_channel_task.delay(channel_id=channel_id)
    return {"status": "enqueued", "task_id": task.id, "channel_id": channel_id}
