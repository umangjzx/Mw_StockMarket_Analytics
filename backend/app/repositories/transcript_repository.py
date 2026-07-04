"""Transcript repository — all DB queries for transcripts and segments."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.transcript import Transcript, TranscriptSegment
from app.repositories.base import BaseRepository


class TranscriptRepository(BaseRepository[Transcript]):

    def __init__(self, session: AsyncSession):
        super().__init__(Transcript, session)

    async def get_by_video_id(self, video_id: int, with_segments: bool = False) -> Transcript | None:
        q = select(Transcript).where(Transcript.video_id == video_id)
        if with_segments:
            q = q.options(selectinload(Transcript.segments))
        result = await self.session.execute(q)
        return result.scalar_one_or_none()

    async def get_segments(
        self,
        transcript_id: int,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TranscriptSegment]:
        result = await self.session.execute(
            select(TranscriptSegment)
            .where(TranscriptSegment.transcript_id == transcript_id)
            .order_by(TranscriptSegment.sequence_no)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_segments(self, transcript_id: int) -> int:
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count()).select_from(TranscriptSegment)
            .where(TranscriptSegment.transcript_id == transcript_id)
        )
        return result.scalar() or 0

    async def save_transcript(
        self,
        video_id: int,
        source: str,
        language: str | None,
        full_text: str,
        word_count: int | None,
        segments: list[dict],  # list of {text, start_seconds, end_seconds, sequence_no}
    ) -> Transcript:
        """
        Atomically delete any existing transcript + segments, then insert fresh.
        This keeps re-running idempotent — no stale segments from a prior run.
        """
        # Delete existing (cascades to segments via FK)
        await self.session.execute(
            delete(Transcript).where(Transcript.video_id == video_id)
        )

        transcript = Transcript(
            video_id=video_id,
            source=source,
            language=language,
            full_text=full_text,
            word_count=word_count,
        )
        self.session.add(transcript)
        await self.session.flush()  # Get the transcript ID

        for seg_data in segments:
            seg = TranscriptSegment(
                transcript_id=transcript.id,
                sequence_no=seg_data["sequence_no"],
                start_seconds=seg_data["start_seconds"],
                end_seconds=seg_data["end_seconds"],
                text=seg_data["text"],
            )
            self.session.add(seg)

        await self.session.flush()
        await self.session.refresh(transcript)
        return transcript
