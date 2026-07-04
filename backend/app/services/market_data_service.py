"""
Market data service — cache-through orchestration over the market data
provider waterfall.

Layering, cheapest to most expensive:
  1. Redis short-TTL cache — hot path, avoids duplicate calls within seconds.
  2. Postgres durable snapshot — always-available fallback + "last updated".
  3. Provider waterfall fetch (yfinance -> Twelve Data).

A short Redis SETNX lock per (ticker_id/company_id, data_type) prevents a
cache stampede when many requests hit the same cold ticker at once — the
"avoid duplicate requests" requirement.

All datetimes are naive UTC, per this project's DB convention (see
SYSTEM-CONTEXT.md — mixing tz-aware and naive datetimes has caused bugs here
before).
"""

import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta

import redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.market_data import CompanyProfile, MarketQuote, PriceBar
from app.providers.market_data.base import MarketDataProvider, OHLCVBar
from app.repositories.market_data_repository import MarketDataRepository

logger = get_logger(__name__)

_LOCK_TTL_SECONDS = 15
_LOCK_WAIT_SECONDS = 0.2
_LOCK_MAX_WAIT_ITERATIONS = 25  # ~5s max wait for an in-flight fetch by another request
_PROFILE_FRESHNESS = timedelta(days=7)     # profiles change rarely
_QUOTE_STALE_FALLBACK_WINDOW = timedelta(hours=1)  # how old a DB snapshot can be and still count as "cached"

PROVIDER_SOURCE_NAME = "yfinance"  # composite provider's primary; used as the attribution label


def _now() -> datetime:
    return datetime.utcnow()


class MarketDataService:

    def __init__(self, session: AsyncSession, provider: MarketDataProvider) -> None:
        self._session = session
        self._provider = provider
        self._repo = MarketDataRepository(session)
        self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)

    # ── Quotes ───────────────────────────────────────────────────────────────

    async def get_quote(self, ticker_id: int, symbol: str, exchange: str | None) -> dict:
        """Returns a dict with quote fields plus `status` ("live"|"cached"|"unavailable").
        Numeric fields are always returned as real numbers — Redis hashes only store
        strings internally, but that's a storage detail, not the API shape."""
        cache_key = f"mkt:quote:{ticker_id}"
        cached = self._redis.hgetall(cache_key)
        if cached:
            return {**_coerce_quote_types(cached), "status": "cached"}

        lock_key = f"mkt:lock:quote:{ticker_id}"
        acquired = bool(self._redis.set(lock_key, "1", nx=True, ex=_LOCK_TTL_SECONDS))

        if not acquired:
            for _ in range(_LOCK_MAX_WAIT_ITERATIONS):
                await asyncio.sleep(_LOCK_WAIT_SECONDS)
                cached = self._redis.hgetall(cache_key)
                if cached:
                    return {**_coerce_quote_types(cached), "status": "cached"}
        else:
            try:
                data = await self._provider.get_quote(symbol, exchange)
                row = await self._repo.upsert_quote(
                    ticker_id, data, source=PROVIDER_SOURCE_NAME, fetched_at=_now()
                )
                await self._session.commit()
                payload = _quote_row_to_flat_dict(row)
                self._redis.hset(cache_key, mapping=payload)
                self._redis.expire(cache_key, settings.MARKET_QUOTE_CACHE_TTL_SECONDS)
                return {**_coerce_quote_types(payload), "status": "live"}
            except Exception as exc:
                logger.warning(
                    "Live quote fetch failed, falling back to last known snapshot",
                    extra={"ticker_id": ticker_id, "symbol": symbol, "error": str(exc)},
                )
            finally:
                self._redis.delete(lock_key)

        # Fallback: last known Postgres snapshot, however old
        row = await self._repo.get_quote(ticker_id)
        if row:
            status = "cached" if (_now() - row.fetched_at) <= _QUOTE_STALE_FALLBACK_WINDOW else "unavailable"
            return {**_coerce_quote_types(_quote_row_to_flat_dict(row)), "status": status}
        return {"status": "unavailable"}

    # ── Company profile ──────────────────────────────────────────────────────

    async def get_profile(self, company_id: int, symbol: str, exchange: str | None) -> dict:
        existing = await self._repo.get_profile(company_id)
        if existing and (_now() - existing.fetched_at) <= _PROFILE_FRESHNESS:
            return {**_profile_row_to_dict(existing), "status": "cached"}

        try:
            data = await self._provider.get_profile(symbol, exchange)
            row = await self._repo.upsert_profile(
                company_id, data, source=PROVIDER_SOURCE_NAME, source_url=None, fetched_at=_now()
            )
            await self._session.commit()
            return {**_profile_row_to_dict(row), "status": "live"}
        except Exception as exc:
            logger.warning(
                "Live profile fetch failed, falling back to last known snapshot",
                extra={"company_id": company_id, "symbol": symbol, "error": str(exc)},
            )
            if existing:
                return {**_profile_row_to_dict(existing), "status": "cached"}
            return {"status": "unavailable"}

    # ── Charts ───────────────────────────────────────────────────────────────

    async def get_chart(
        self, ticker_id: int, symbol: str, exchange: str | None, chart_range: str
    ) -> tuple[list[dict], str]:
        """Returns (bars, status). Daily+ ranges (1M-5Y) are served from the
        persisted, beat-refreshed price_bars table when available. Intraday
        (1D/1W) and MAX are fetched live with a short Redis cache — they're
        either too granular or too rare to be worth persisting."""
        if chart_range in ("1M", "3M", "6M", "1Y", "5Y"):
            since = _now() - _RANGE_TO_TIMEDELTA[chart_range]
            bars = await self._repo.get_daily_bars(ticker_id, since=since)
            if bars:
                return [_bar_row_to_dict(b) for b in bars], "cached"
            # Cold ticker — nothing persisted yet, fetch live and seed the table
            try:
                fetched = await self._provider.get_history(symbol, exchange, "5Y")
                await self._repo.upsert_daily_bars(ticker_id, fetched)
                await self._session.commit()
                bars = await self._repo.get_daily_bars(ticker_id, since=since)
                return [_bar_row_to_dict(b) for b in bars], "live"
            except Exception as exc:
                logger.warning("Live chart backfill failed", extra={"ticker_id": ticker_id, "error": str(exc)})
                return [], "unavailable"

        # Intraday / MAX — Redis-cached, not persisted
        cache_key = f"mkt:chart:{ticker_id}:{chart_range}"
        cached = self._redis.get(cache_key)
        if cached:
            import json
            return json.loads(cached), "cached"

        try:
            fetched = await self._provider.get_history(symbol, exchange, chart_range)
            payload = [asdict(b) for b in fetched]
            import json
            self._redis.set(cache_key, json.dumps(payload, default=str), ex=settings.MARKET_QUOTE_CACHE_TTL_SECONDS)
            return [_bar_dataclass_to_dict(b) for b in fetched], "live"
        except Exception as exc:
            logger.warning("Live intraday chart fetch failed", extra={"ticker_id": ticker_id, "error": str(exc)})
            return [], "unavailable"

    async def refresh_daily_bars_now(self, ticker_id: int, symbol: str, exchange: str | None) -> int:
        """Unconditionally re-fetch and upsert the persisted daily series —
        used by the scheduled refresh task. Unlike get_chart(), this always
        hits the provider so today's bar gets appended even when bars already
        exist (get_chart's cold-start backfill only fires when the table is
        empty)."""
        fetched = await self._provider.get_history(symbol, exchange, "5Y")
        count = await self._repo.upsert_daily_bars(ticker_id, fetched)
        await self._session.commit()
        return count


_RANGE_TO_TIMEDELTA = {
    "1M": timedelta(days=31),
    "3M": timedelta(days=93),
    "6M": timedelta(days=186),
    "1Y": timedelta(days=366),
    "5Y": timedelta(days=366 * 5),
}


_QUOTE_FLOAT_FIELDS = {
    "price", "change_abs", "change_pct", "open", "high", "low", "prev_close",
    "market_cap", "week52_high", "week52_low", "bid", "ask", "vwap",
    "pre_market_price", "after_hours_price",
}
_QUOTE_INT_FIELDS = {"volume"}


def _coerce_quote_types(flat: dict) -> dict:
    """Convert the flat all-string dict (as stored in a Redis hash) back into
    real numeric types for the API response."""
    out: dict = {}
    for key, value in flat.items():
        if value in (None, ""):
            out[key] = None
        elif key in _QUOTE_FLOAT_FIELDS:
            out[key] = float(value)
        elif key in _QUOTE_INT_FIELDS:
            out[key] = int(float(value))
        else:
            out[key] = value
    return out


def _quote_row_to_flat_dict(row: MarketQuote) -> dict:
    """Redis hashes require flat string values."""
    return {
        k: ("" if v is None else str(v))
        for k, v in {
            "price": row.price, "change_abs": row.change_abs, "change_pct": row.change_pct,
            "open": row.open, "high": row.high, "low": row.low, "prev_close": row.prev_close,
            "volume": row.volume, "market_cap": row.market_cap,
            "week52_high": row.week52_high, "week52_low": row.week52_low,
            "bid": row.bid, "ask": row.ask, "vwap": row.vwap,
            "pre_market_price": row.pre_market_price, "after_hours_price": row.after_hours_price,
            "currency": row.currency, "source": row.source, "fetched_at": row.fetched_at.isoformat(),
        }.items()
    }


def _profile_row_to_dict(row: CompanyProfile) -> dict:
    return {
        "description": row.description, "ceo": row.ceo, "headquarters": row.headquarters,
        "employees": row.employees, "website": row.website, "primary_exchange": row.primary_exchange,
        "ipo_date": row.ipo_date.isoformat() if row.ipo_date else None,
        "business_segments": row.business_segments or [],
        "source": row.source, "source_url": row.source_url, "fetched_at": row.fetched_at.isoformat(),
    }


def _bar_row_to_dict(row: PriceBar) -> dict:
    return {
        "ts": row.ts.isoformat(), "open": float(row.open), "high": float(row.high),
        "low": float(row.low), "close": float(row.close), "volume": row.volume,
    }


def _bar_dataclass_to_dict(bar: OHLCVBar) -> dict:
    return {
        "ts": bar.ts.isoformat(), "open": bar.open, "high": bar.high,
        "low": bar.low, "close": bar.close, "volume": bar.volume,
    }
