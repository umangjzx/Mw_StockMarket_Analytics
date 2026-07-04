"""
Analyst insights service — cache-through fetch of consensus, price targets,
upgrades/downgrades, institutional ownership, and insider transactions.
Same freshness principle as ratios: this data moves on analyst-report
cadence, not tick-by-tick, so a Postgres freshness check is enough.
"""

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.news_analyst import AnalystSnapshot
from app.providers.market_data.base import MarketDataProvider
from app.repositories.analyst_repository import AnalystRepository

logger = get_logger(__name__)

_FRESHNESS = timedelta(hours=20)
PROVIDER_SOURCE_NAME = "yfinance"


def _now() -> datetime:
    return datetime.utcnow()


class AnalystService:

    def __init__(self, session: AsyncSession, provider: MarketDataProvider) -> None:
        self._session = session
        self._provider = provider
        self._repo = AnalystRepository(session)

    async def get_analyst_insights(self, ticker_id: int, symbol: str, exchange: str | None) -> dict:
        existing = await self._repo.get(ticker_id)
        if existing and (_now() - existing.fetched_at) <= _FRESHNESS:
            return {**_row_to_dict(existing), "status": "cached"}

        try:
            data = await self._provider.get_analyst_insights(symbol, exchange)
            row = await self._repo.upsert(ticker_id, data, source=PROVIDER_SOURCE_NAME, fetched_at=_now())
            await self._session.commit()
            return {**_row_to_dict(row), "status": "live"}
        except Exception as exc:
            logger.warning(
                "Live analyst insights fetch failed, falling back",
                extra={"ticker_id": ticker_id, "error": str(exc)},
            )
            if existing:
                return {**_row_to_dict(existing), "status": "cached"}
            return {"status": "unavailable"}


def _row_to_dict(row: AnalystSnapshot) -> dict:
    return {
        "recommendation_mean": _f(row.recommendation_mean),
        "recommendation_key": row.recommendation_key,
        "target_mean": _f(row.target_mean),
        "target_high": _f(row.target_high),
        "target_low": _f(row.target_low),
        "target_median": _f(row.target_median),
        "num_analyst_opinions": row.num_analyst_opinions,
        "held_pct_institutions": _f(row.held_pct_institutions),
        "held_pct_insiders": _f(row.held_pct_insiders),
        "recommendation_trend": row.recommendation_trend or [],
        "actions": row.actions or [],
        "institutional_holders": row.institutional_holders or [],
        "insider_transactions": row.insider_transactions or [],
        "source": row.source,
        "fetched_at": row.fetched_at.isoformat(),
    }


def _f(value) -> float | None:
    return float(value) if value is not None else None
