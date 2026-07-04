"""Analyst insights repository — CRUD for the 1:1 analyst_snapshots table."""

from dataclasses import asdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_analyst import AnalystSnapshot
from app.providers.market_data.base import AnalystInsightsData


class AnalystRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, ticker_id: int) -> AnalystSnapshot | None:
        result = await self._session.execute(
            select(AnalystSnapshot).where(AnalystSnapshot.ticker_id == ticker_id)
        )
        return result.scalar_one_or_none()

    async def upsert(
        self, ticker_id: int, data: AnalystInsightsData, source: str, fetched_at: datetime
    ) -> AnalystSnapshot:
        existing = await self.get(ticker_id)
        fields = dict(
            recommendation_mean=data.recommendation_mean,
            recommendation_key=data.recommendation_key,
            target_mean=data.target_mean,
            target_high=data.target_high,
            target_low=data.target_low,
            target_median=data.target_median,
            num_analyst_opinions=data.num_analyst_opinions,
            held_pct_institutions=data.held_pct_institutions,
            held_pct_insiders=data.held_pct_insiders,
            recommendation_trend=[asdict(p) for p in data.recommendation_trend],
            actions=[
                {**asdict(a), "grade_date": a.grade_date.isoformat()}
                for a in data.actions
            ],
            institutional_holders=[
                {**asdict(h), "date_reported": h.date_reported.isoformat() if h.date_reported else None}
                for h in data.institutional_holders
            ],
            insider_transactions=[
                {**asdict(i), "start_date": i.start_date.isoformat() if i.start_date else None}
                for i in data.insider_transactions
            ],
            source=source,
            fetched_at=fetched_at,
        )
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            await self._session.flush()
            return existing

        row = AnalystSnapshot(ticker_id=ticker_id, **fields)
        self._session.add(row)
        await self._session.flush()
        return row
