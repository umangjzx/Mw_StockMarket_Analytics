"""Video repository — all DB queries for videos."""

from datetime import datetime

from sqlalchemy import and_, select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.video import Video
from app.models.video_stat_snapshot import VideoStatSnapshot
from app.repositories.base import BaseRepository


class VideoRepository(BaseRepository[Video]):

    def __init__(self, session: AsyncSession):
        super().__init__(Video, session)

    async def get_by_external_id(self, channel_id: int, external_video_id: str) -> Video | None:
        result = await self.session.execute(
            select(Video).where(
                Video.channel_id == channel_id,
                Video.external_video_id == external_video_id,
            )
        )
        return result.scalar_one_or_none()

    async def find_by_external_id(self, external_video_id: str) -> Video | None:
        """Find video by external ID only (across all channels)."""
        result = await self.session.execute(
            select(Video).where(Video.external_video_id == external_video_id)
        )
        return result.scalar_one_or_none()

    async def get_by_ids(
        self, video_ids: list[int], pipeline_status: str | None = None
    ) -> list[Video]:
        """Bulk-fetch videos by ID, e.g. all videos mentioning a given company."""
        if not video_ids:
            return []
        q = select(Video).options(selectinload(Video.channel)).where(Video.id.in_(video_ids))
        if pipeline_status:
            q = q.where(Video.pipeline_status == pipeline_status)
        q = q.order_by(Video.published_at.desc())
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get_known_ids(self, channel_id: int) -> set[str]:
        """Return the set of external_video_ids already in the DB for this channel."""
        result = await self.session.execute(
            select(Video.external_video_id).where(Video.channel_id == channel_id)
        )
        return {row[0] for row in result.fetchall()}

    async def list_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        channel_id: int | None = None,
        pipeline_status: str | None = None,
        content_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sort: str = "-published_at",
    ) -> tuple[list[Video], int]:
        q = select(Video)
        count_q = select(func.count()).select_from(Video)

        filters = []
        if channel_id:
            filters.append(Video.channel_id == channel_id)
        if pipeline_status:
            filters.append(Video.pipeline_status == pipeline_status)
        if content_type:
            filters.append(Video.content_type == content_type)
        if date_from:
            filters.append(Video.published_at >= date_from)
        if date_to:
            filters.append(Video.published_at <= date_to)

        if filters:
            q = q.where(and_(*filters))
            count_q = count_q.where(and_(*filters))

        # Sorting
        if sort.startswith("-"):
            col = getattr(Video, sort[1:], None)
            if col is not None:
                q = q.order_by(col.desc())
        else:
            col = getattr(Video, sort, None)
            if col is not None:
                q = q.order_by(col)

        q = q.limit(page_size).offset((page - 1) * page_size)

        results = await self.session.execute(q)
        count_result = await self.session.execute(count_q)
        return list(results.scalars().all()), count_result.scalar() or 0

    async def list_failed(
        self,
        max_retries: int | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[Video], int]:
        q = select(Video).where(Video.pipeline_status == "FAILED")
        count_q = select(func.count()).select_from(Video).where(Video.pipeline_status == "FAILED")

        if max_retries is not None:
            q = q.where(Video.pipeline_retry_count < max_retries)
            count_q = count_q.where(Video.pipeline_retry_count < max_retries)

        q = q.order_by(Video.updated_at.desc()).limit(page_size).offset((page - 1) * page_size)
        results = await self.session.execute(q)
        count_result = await self.session.execute(count_q)
        return list(results.scalars().all()), count_result.scalar() or 0

    async def list_retryable(self, max_retries: int) -> list[Video]:
        """Videos that failed and are due for retry (next_retry_at <= now)."""
        from datetime import UTC
        now = datetime.now(UTC)
        result = await self.session.execute(
            select(Video).where(
                Video.pipeline_status == "FAILED",
                Video.pipeline_retry_count < max_retries,
                Video.pipeline_next_retry_at <= now,
            ).order_by(Video.pipeline_next_retry_at)
        )
        return list(result.scalars().all())

    async def list_recently_published(self, days: int = 14) -> list[Video]:
        """Videos published within the last N days (for stat refresh)."""
        from datetime import UTC, timedelta
        cutoff = datetime.now(UTC) - timedelta(days=days)
        result = await self.session.execute(
            select(Video)
            .where(Video.published_at >= cutoff)
            .where(Video.pipeline_status == "INDEXED")
        )
        return list(result.scalars().all())

    async def upsert_discovered(
        self, channel_id: int, external_video_id: str, defaults: dict
    ) -> tuple[Video, bool]:
        """
        Insert a newly discovered video or update metadata if it already exists.
        Returns (video, created).
        """
        existing = await self.get_by_external_id(channel_id, external_video_id)
        if existing:
            for key, value in defaults.items():
                setattr(existing, key, value)
            await self.session.flush()
            await self.session.refresh(existing)
            return existing, False
        else:
            video = Video(
                channel_id=channel_id,
                external_video_id=external_video_id,
                pipeline_status="DISCOVERED",
                **defaults,
            )
            self.session.add(video)
            await self.session.flush()
            await self.session.refresh(video)
            return video, True

    async def set_pipeline_status(
        self,
        video_id: int,
        status: str,
        failure_reason: str | None = None,
        next_retry_at: datetime | None = None,
    ) -> None:
        """Update the pipeline status of a video."""
        values: dict = {"pipeline_status": status}
        if failure_reason is not None:
            values["pipeline_failure_reason"] = failure_reason
        if next_retry_at is not None:
            values["pipeline_next_retry_at"] = next_retry_at
        if status == "FAILED":
            values["pipeline_retry_count"] = Video.pipeline_retry_count + 1  # type: ignore[assignment]
        await self.session.execute(
            update(Video).where(Video.id == video_id).values(**values)
        )

    async def update_stats(
        self,
        video_id: int,
        view_count: int | None,
        like_count: int | None,
        comment_count: int | None,
    ) -> None:
        """Update denormalized stats on the video row."""
        await self.session.execute(
            update(Video).where(Video.id == video_id).values(
                view_count=view_count,
                like_count=like_count,
                comment_count=comment_count,
            )
        )

    async def count_by_status(self) -> dict[str, int]:
        """Return {pipeline_status: count} for admin dashboard."""
        result = await self.session.execute(
            select(Video.pipeline_status, func.count()).group_by(Video.pipeline_status)
        )
        return {row[0]: row[1] for row in result.fetchall()}

    async def add_stat_snapshot(
        self,
        video_id: int,
        view_count: int | None,
        like_count: int | None,
        comment_count: int | None,
    ) -> VideoStatSnapshot:
        snapshot = VideoStatSnapshot(
            video_id=video_id,
            view_count=view_count,
            like_count=like_count,
            comment_count=comment_count,
        )
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot
