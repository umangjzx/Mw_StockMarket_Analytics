"""
Composite market data provider — waterfall across yfinance (primary) and
Twelve Data (fallback), mirroring the transcription waterfall pattern in
app/services/transcript_service.py (YouTube captions -> Whisper).

The fallback only ever engages if TWELVE_DATA_API_KEY is configured; with no
key set, this is a thin pass-through to yfinance alone.
"""

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.market_data.base import (
    AnalystInsightsData,
    CompanyProfileData,
    EarningsData,
    FinancialPeriod,
    MarketDataProvider,
    NewsArticle,
    OHLCVBar,
    QuoteData,
    RatiosData,
    SymbolMatch,
)
from app.providers.market_data.yfinance_provider import YFinanceProvider

logger = get_logger(__name__)


def build_market_data_provider() -> "CompositeMarketDataProvider":
    """Construct the composite provider from current settings."""
    fallback = None
    if settings.TWELVE_DATA_API_KEY:
        from app.providers.market_data.twelvedata_provider import TwelveDataProvider
        fallback = TwelveDataProvider()
    return CompositeMarketDataProvider(primary=YFinanceProvider(), fallback=fallback)


class CompositeMarketDataProvider(MarketDataProvider):

    def __init__(self, primary: MarketDataProvider, fallback: MarketDataProvider | None) -> None:
        self._primary = primary
        self._fallback = fallback

    async def search_symbol(self, query: str) -> list[SymbolMatch]:
        try:
            results = await self._primary.search_symbol(query)
            if results:
                return results
        except Exception as exc:
            logger.warning("Primary search_symbol failed, trying fallback", extra={"error": str(exc)})

        if self._fallback:
            try:
                return await self._fallback.search_symbol(query)
            except Exception as exc:
                logger.warning("Fallback search_symbol also failed", extra={"error": str(exc)})
        return []

    async def get_quote(self, symbol: str, exchange: str | None) -> QuoteData:
        try:
            return await self._primary.get_quote(symbol, exchange)
        except Exception as exc:
            logger.warning(
                "Primary get_quote failed, trying fallback",
                extra={"symbol": symbol, "exchange": exchange, "error": str(exc)},
            )
            if not self._fallback:
                raise
            return await self._fallback.get_quote(symbol, exchange)

    async def get_history(
        self,
        symbol: str,
        exchange: str | None,
        chart_range: str,
        interval: str | None = None,
    ) -> list[OHLCVBar]:
        primary_exc: Exception | None = None
        try:
            bars = await self._primary.get_history(symbol, exchange, chart_range, interval)
            if bars:
                return bars
        except Exception as exc:
            primary_exc = exc
            logger.warning(
                "Primary get_history failed, trying fallback",
                extra={"symbol": symbol, "exchange": exchange, "range": chart_range, "error": str(exc)},
            )

        if self._fallback:
            return await self._fallback.get_history(symbol, exchange, chart_range, interval)
        if primary_exc:
            raise primary_exc
        return []

    async def get_profile(self, symbol: str, exchange: str | None) -> CompanyProfileData:
        try:
            return await self._primary.get_profile(symbol, exchange)
        except Exception as exc:
            logger.warning(
                "Primary get_profile failed, trying fallback",
                extra={"symbol": symbol, "exchange": exchange, "error": str(exc)},
            )
            if not self._fallback:
                raise
            return await self._fallback.get_profile(symbol, exchange)

    async def get_ratios(self, symbol: str, exchange: str | None) -> RatiosData:
        try:
            return await self._primary.get_ratios(symbol, exchange)
        except Exception as exc:
            logger.warning(
                "Primary get_ratios failed, trying fallback",
                extra={"symbol": symbol, "exchange": exchange, "error": str(exc)},
            )
            if not self._fallback:
                raise
            return await self._fallback.get_ratios(symbol, exchange)

    async def get_financial_statements(
        self, symbol: str, exchange: str | None, statement_type: str, period: str
    ) -> list[FinancialPeriod]:
        try:
            periods = await self._primary.get_financial_statements(symbol, exchange, statement_type, period)
            if periods:
                return periods
        except Exception as exc:
            logger.warning(
                "Primary get_financial_statements failed, trying fallback",
                extra={"symbol": symbol, "exchange": exchange, "statement": statement_type, "error": str(exc)},
            )

        if self._fallback:
            return await self._fallback.get_financial_statements(symbol, exchange, statement_type, period)
        return []

    async def get_earnings(self, symbol: str, exchange: str | None) -> EarningsData:
        try:
            return await self._primary.get_earnings(symbol, exchange)
        except Exception as exc:
            logger.warning(
                "Primary get_earnings failed, trying fallback",
                extra={"symbol": symbol, "exchange": exchange, "error": str(exc)},
            )
            if not self._fallback:
                raise
            return await self._fallback.get_earnings(symbol, exchange)

    async def get_news(self, symbol: str, exchange: str | None, limit: int = 10) -> list[NewsArticle]:
        try:
            articles = await self._primary.get_news(symbol, exchange, limit)
            if articles:
                return articles
        except Exception as exc:
            logger.warning(
                "Primary get_news failed, trying fallback",
                extra={"symbol": symbol, "exchange": exchange, "error": str(exc)},
            )

        if self._fallback:
            return await self._fallback.get_news(symbol, exchange, limit)
        return []

    async def get_analyst_insights(self, symbol: str, exchange: str | None) -> AnalystInsightsData:
        try:
            return await self._primary.get_analyst_insights(symbol, exchange)
        except Exception as exc:
            logger.warning(
                "Primary get_analyst_insights failed, trying fallback",
                extra={"symbol": symbol, "exchange": exchange, "error": str(exc)},
            )
            if not self._fallback:
                raise
            return await self._fallback.get_analyst_insights(symbol, exchange)
