"""
Market data refresh tasks — scheduled background updates for the Company
Intelligence module, scoped to tickers someone is actually watching (any
WatchlistItem) rather than every ticker ever mentioned by a video, which
would waste calls refreshing tickers nobody's looking at.
"""

import asyncio

from celery import Task

from app.core.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)


async def _get_watched_tickers(session) -> list:
    """Distinct tickers present in any user's watchlist, with company_id for profile refresh."""
    from sqlalchemy import select
    from app.models.company import Ticker
    from app.models.user import WatchlistItem

    result = await session.execute(
        select(Ticker)
        .join(WatchlistItem, WatchlistItem.ticker_id == Ticker.id)
        .distinct()
    )
    return list(result.scalars().all())


@celery_app.task(
    name="app.workers.tasks.market_data_tasks.refresh_watched_quotes",
    bind=True,
)
def refresh_watched_quotes(self: Task) -> dict:
    """Refresh live quotes for every watched ticker."""
    return asyncio.run(_refresh_watched_quotes_async())


async def _refresh_watched_quotes_async() -> dict:
    from app.db.session import create_worker_session
    from app.providers.market_data.composite_provider import build_market_data_provider
    from app.services.market_data_service import MarketDataService

    provider = build_market_data_provider()
    refreshed, failed = 0, 0

    async with create_worker_session() as session:
        service = MarketDataService(session, provider)
        tickers = await _get_watched_tickers(session)

        if not tickers:
            logger.info("No watched tickers — skipping quote refresh")
            return {"status": "ok", "refreshed": 0}

        for ticker in tickers:
            try:
                await service.get_quote(ticker.id, ticker.symbol, ticker.exchange)
                refreshed += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "Watched quote refresh failed",
                    extra={"ticker_id": ticker.id, "symbol": ticker.symbol, "error": str(exc)},
                )

    logger.info("Watched quotes refreshed", extra={"refreshed": refreshed, "failed": failed})
    return {"status": "ok", "refreshed": refreshed, "failed": failed}


@celery_app.task(
    name="app.workers.tasks.market_data_tasks.refresh_daily_bars",
    bind=True,
)
def refresh_daily_bars(self: Task) -> dict:
    """Refresh persisted daily OHLCV bars for every watched ticker."""
    return asyncio.run(_refresh_daily_bars_async())


async def _refresh_daily_bars_async() -> dict:
    from app.db.session import create_worker_session
    from app.providers.market_data.composite_provider import build_market_data_provider
    from app.services.market_data_service import MarketDataService

    provider = build_market_data_provider()
    refreshed, failed = 0, 0

    async with create_worker_session() as session:
        service = MarketDataService(session, provider)
        tickers = await _get_watched_tickers(session)

        if not tickers:
            logger.info("No watched tickers — skipping daily bar refresh")
            return {"status": "ok", "refreshed": 0}

        for ticker in tickers:
            try:
                await service.refresh_daily_bars_now(ticker.id, ticker.symbol, ticker.exchange)
                refreshed += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "Watched daily bar refresh failed",
                    extra={"ticker_id": ticker.id, "symbol": ticker.symbol, "error": str(exc)},
                )

    logger.info("Watched daily bars refreshed", extra={"refreshed": refreshed, "failed": failed})
    return {"status": "ok", "refreshed": refreshed, "failed": failed}


@celery_app.task(
    name="app.workers.tasks.market_data_tasks.refresh_company_profiles",
    bind=True,
)
def refresh_company_profiles(self: Task) -> dict:
    """Refresh company overview profiles for every watched ticker's company. Profiles
    change rarely; MarketDataService.get_profile() already no-ops if the existing
    snapshot is under 7 days old, so calling this weekly is enough."""
    return asyncio.run(_refresh_company_profiles_async())


async def _refresh_company_profiles_async() -> dict:
    from app.db.session import create_worker_session
    from app.providers.market_data.composite_provider import build_market_data_provider
    from app.services.market_data_service import MarketDataService

    provider = build_market_data_provider()
    refreshed, skipped, failed = 0, 0, 0

    async with create_worker_session() as session:
        service = MarketDataService(session, provider)
        tickers = await _get_watched_tickers(session)

        if not tickers:
            logger.info("No watched tickers — skipping profile refresh")
            return {"status": "ok", "refreshed": 0}

        for ticker in tickers:
            if not ticker.company_id:
                skipped += 1
                continue
            try:
                await service.get_profile(ticker.company_id, ticker.symbol, ticker.exchange)
                refreshed += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "Watched profile refresh failed",
                    extra={"ticker_id": ticker.id, "symbol": ticker.symbol, "error": str(exc)},
                )

    logger.info(
        "Watched company profiles refreshed",
        extra={"refreshed": refreshed, "skipped": skipped, "failed": failed},
    )
    return {"status": "ok", "refreshed": refreshed, "skipped": skipped, "failed": failed}
