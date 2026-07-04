"""Executive summary repository — CRUD for the 1:1 executive_summaries table."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_analyst import ExecutiveSummary


class ExecutiveSummaryRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, ticker_id: int) -> ExecutiveSummary | None:
        result = await self._session.execute(
            select(ExecutiveSummary).where(ExecutiveSummary.ticker_id == ticker_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self, ticker_id: int, fields: dict, source: str, fetched_at: datetime
    ) -> ExecutiveSummary:
        existing = await self.get(ticker_id)
        all_fields = {**fields, "source": source, "fetched_at": fetched_at}
        if existing:
            for key, value in all_fields.items():
                setattr(existing, key, value)
            await self._session.flush()
            return existing

        row = ExecutiveSummary(ticker_id=ticker_id, **all_fields)
        self._session.add(row)
        await self._session.flush()
        return row
