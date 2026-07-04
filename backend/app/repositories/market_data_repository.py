"""
Market data repository — CRUD for company_profiles, market_quotes, and
price_bars. Only "1d" interval bars are persisted (covering 1M-5Y chart
ranges by filtering on fetch); intraday and MAX ranges are served live with a
short Redis cache in MarketDataService rather than persisted here, to avoid
unbounded row growth for low long-term value.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market_data import CompanyProfile, MarketQuote, PriceBar
from app.providers.market_data.base import CompanyProfileData, OHLCVBar, QuoteData

DAILY_INTERVAL = "1d"


class MarketDataRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Quotes ───────────────────────────────────────────────────────────────

    async def get_quote(self, ticker_id: int) -> MarketQuote | None:
        result = await self._session.execute(
            select(MarketQuote).where(MarketQuote.ticker_id == ticker_id)
        )
        return result.scalar_one_or_none()

    async def upsert_quote(
        self, ticker_id: int, data: QuoteData, source: str, fetched_at: datetime
    ) -> MarketQuote:
        existing = await self.get_quote(ticker_id)
        fields = dict(
            price=data.price,
            change_abs=data.change_abs,
            change_pct=data.change_pct,
            open=data.open,
            high=data.high,
            low=data.low,
            prev_close=data.prev_close,
            volume=data.volume,
            market_cap=data.market_cap,
            week52_high=data.week52_high,
            week52_low=data.week52_low,
            bid=data.bid,
            ask=data.ask,
            vwap=data.vwap,
            pre_market_price=data.pre_market_price,
            after_hours_price=data.after_hours_price,
            currency=data.currency,
            source=source,
            fetched_at=fetched_at,
        )
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            await self._session.flush()
            return existing

        quote = MarketQuote(ticker_id=ticker_id, **fields)
        self._session.add(quote)
        await self._session.flush()
        return quote

    # ── Profiles ─────────────────────────────────────────────────────────────

    async def get_profile(self, company_id: int) -> CompanyProfile | None:
        result = await self._session.execute(
            select(CompanyProfile).where(CompanyProfile.company_id == company_id)
        )
        return result.scalar_one_or_none()

    async def upsert_profile(
        self,
        company_id: int,
        data: CompanyProfileData,
        source: str,
        source_url: str | None,
        fetched_at: datetime,
    ) -> CompanyProfile:
        existing = await self.get_profile(company_id)
        fields = dict(
            description=data.description,
            ceo=data.ceo,
            headquarters=data.headquarters,
            employees=data.employees,
            website=data.website,
            primary_exchange=data.primary_exchange,
            ipo_date=data.ipo_date,
            business_segments=data.business_segments or [],
            source=source,
            source_url=source_url,
            fetched_at=fetched_at,
        )
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            await self._session.flush()
            return existing

        profile = CompanyProfile(company_id=company_id, **fields)
        self._session.add(profile)
        await self._session.flush()
        return profile

    # ── Price bars (daily only) ───────────────────────────────────────────────

    async def get_daily_bars(
        self, ticker_id: int, since: datetime | None = None
    ) -> list[PriceBar]:
        query = (
            select(PriceBar)
            .where(PriceBar.ticker_id == ticker_id, PriceBar.interval == DAILY_INTERVAL)
            .order_by(PriceBar.ts)
        )
        if since is not None:
            query = query.where(PriceBar.ts >= since)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def upsert_daily_bars(self, ticker_id: int, bars: list[OHLCVBar]) -> int:
        """Bulk upsert on (ticker_id, interval, ts) — revises today's/recent bars in place."""
        if not bars:
            return 0

        rows = [
            {
                "ticker_id": ticker_id,
                "interval": DAILY_INTERVAL,
                "ts": bar.ts,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ]

        stmt = pg_insert(PriceBar).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_price_bars_ticker_interval_ts",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return len(rows)
