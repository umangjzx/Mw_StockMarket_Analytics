"""Channel repository — all DB queries for channels."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import Channel
from app.repositories.base import BaseRepository


class ChannelRepository(BaseRepository[Channel]):

    def __init__(self, session: AsyncSession):
        super().__init__(Channel, session)

    async def get_by_external_id(self, platform: str, external_channel_id: str) -> Channel | None:
        result = await self.session.execute(
            select(Channel).where(
                Channel.platform == platform,
                Channel.external_channel_id == external_channel_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_handle(self, handle: str) -> Channel | None:
        result = await self.session.execute(
            select(Channel).where(Channel.handle == handle)
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Channel]:
        """Return all active channels ordered by id."""
        result = await self.session.execute(
            select(Channel).where(Channel.is_active.is_(True)).order_by(Channel.id)
        )
        return list(result.scalars().all())

    async def list_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = False,
    ) -> tuple[list[Channel], int]:
        """Return (channels, total_count) for pagination."""
        from sqlalchemy import func
        q = select(Channel)
        count_q = select(func.count()).select_from(Channel)
        if active_only:
            q = q.where(Channel.is_active.is_(True))
            count_q = count_q.where(Channel.is_active.is_(True))

        q = q.order_by(Channel.id).limit(page_size).offset((page - 1) * page_size)

        results = await self.session.execute(q)
        count_result = await self.session.execute(count_q)

        return list(results.scalars().all()), count_result.scalar() or 0

    async def mark_polled(self, channel_id: int, success: bool = True) -> None:
        """Update last_polled_at and optionally last_successful_poll_at."""
        from datetime import UTC, datetime
        now = datetime.now(UTC)
        values: dict = {"last_polled_at": now, "updated_at": now}
        if success:
            values["last_successful_poll_at"] = now
        await self.session.execute(
            update(Channel).where(Channel.id == channel_id).values(**values)
        )

    async def upsert(
        self,
        platform: str,
        external_channel_id: str,
        defaults: dict,
    ) -> tuple[Channel, bool]:
        """
        Insert or update a channel. Returns (channel, created).
        `defaults` is applied on both insert and update.
        """
        existing = await self.get_by_external_id(platform, external_channel_id)
        if existing:
            for key, value in defaults.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing, False
        else:
            channel = Channel(
                platform=platform,
                external_channel_id=external_channel_id,
                **defaults,
            )
            self.session.add(channel)
            await self.session.flush()
            await self.session.refresh(channel)
            return channel, True
