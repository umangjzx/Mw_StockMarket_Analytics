"""
Twelve Data market data provider — fallback for when yfinance is unavailable
or blocked. Requires TWELVE_DATA_API_KEY; the composite provider skips this
adapter entirely when the key is unset.

Free tier covers global exchanges (including NSE) for quotes and time series,
but fundamentals/profile endpoints are Grow-tier+ — profile calls are
best-effort and will raise ExternalServiceError on a plan-restriction
response, which the caller treats as "unavailable" rather than a hard error.
"""

import httpx

from app.core.config import settings
from app.core.exceptions import ExternalServiceError
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

logger = get_logger(__name__)

BASE_URL = "https://api.twelvedata.com"

_EXCHANGE_MIC = {"NSE": "NSE", "BSE": "BSE"}

# Chart range -> (interval, outputsize) tuned to keep payloads small
_RANGE_MAP: dict[str, tuple[str, int]] = {
    "1D": ("5min", 80),
    "1W": ("30min", 70),
    "1M": ("1day", 22),
    "3M": ("1day", 66),
    "6M": ("1day", 130),
    "1Y": ("1day", 252),
    "5Y": ("1week", 260),
    "MAX": ("1month", 240),
}


def _to_td_symbol(symbol: str, exchange: str | None) -> str:
    # Substring match, not exact — some existing ticker rows (populated by the
    # video-analysis pipeline, not this module) store combined exchange
    # strings like "NSE|BSE".
    exch = (exchange or "").upper()
    for code, mic in _EXCHANGE_MIC.items():
        if code in exch:
            return f"{symbol.upper()}:{mic}"
    return symbol.upper()


class TwelveDataProvider(MarketDataProvider):

    def __init__(self) -> None:
        self._api_key = settings.TWELVE_DATA_API_KEY

    async def _get(self, path: str, params: dict) -> dict:
        params = {**params, "apikey": self._api_key}
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{BASE_URL}/{path}", params=params)
            resp.raise_for_status()
            data = resp.json()
        if isinstance(data, dict) and data.get("status") == "error":
            raise ExternalServiceError(f"Twelve Data error on {path}: {data.get('message')}")
        return data

    async def search_symbol(self, query: str) -> list[SymbolMatch]:
        try:
            data = await self._get("symbol_search", {"symbol": query})
        except Exception as exc:
            logger.warning("Twelve Data symbol_search failed", extra={"query": query, "error": str(exc)})
            return []

        matches = []
        for item in data.get("data", [])[:8]:
            exchange = item.get("exchange")
            matches.append(SymbolMatch(
                symbol=item.get("symbol", ""),
                exchange=exchange,
                name=item.get("instrument_name", ""),
                provider_symbol=_to_td_symbol(item.get("symbol", ""), exchange),
            ))
        return matches

    async def get_quote(self, symbol: str, exchange: str | None) -> QuoteData:
        td_symbol = _to_td_symbol(symbol, exchange)
        try:
            data = await self._get("quote", {"symbol": td_symbol})
        except Exception as exc:
            raise ExternalServiceError(f"Twelve Data quote failed for {td_symbol}: {exc}") from exc

        if not data or "close" not in data:
            raise ExternalServiceError(f"Twelve Data returned no quote for {td_symbol}")

        week52 = data.get("fifty_two_week") or {}

        def _f(key: str) -> float | None:
            val = data.get(key)
            return float(val) if val not in (None, "") else None

        return QuoteData(
            price=_f("close"),
            change_abs=_f("change"),
            change_pct=_f("percent_change"),
            open=_f("open"),
            high=_f("high"),
            low=_f("low"),
            prev_close=_f("previous_close"),
            volume=int(data["volume"]) if data.get("volume") else None,
            week52_high=float(week52["high"]) if week52.get("high") else None,
            week52_low=float(week52["low"]) if week52.get("low") else None,
            currency=data.get("currency"),
        )

    async def get_history(
        self,
        symbol: str,
        exchange: str | None,
        chart_range: str,
        interval: str | None = None,
    ) -> list[OHLCVBar]:
        if chart_range not in _RANGE_MAP:
            raise ValueError(f"Unsupported chart range: {chart_range}")
        td_symbol = _to_td_symbol(symbol, exchange)
        default_interval, outputsize = _RANGE_MAP[chart_range]
        resolved_interval = interval or default_interval

        try:
            data = await self._get(
                "time_series",
                {"symbol": td_symbol, "interval": resolved_interval, "outputsize": outputsize},
            )
        except Exception as exc:
            raise ExternalServiceError(
                f"Twelve Data history failed for {td_symbol} ({resolved_interval}): {exc}"
            ) from exc

        bars = []
        for row in data.get("values", []):
            try:
                from datetime import datetime as _dt, timezone as _tz
                ts = _dt.fromisoformat(row["datetime"])
                if ts.tzinfo is not None:
                    ts = ts.astimezone(_tz.utc).replace(tzinfo=None)
            except (KeyError, ValueError):
                continue
            bars.append(OHLCVBar(
                ts=ts,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]) if row.get("volume") else None,
            ))
        bars.reverse()  # Twelve Data returns newest-first
        return bars

    async def get_profile(self, symbol: str, exchange: str | None) -> CompanyProfileData:
        td_symbol = _to_td_symbol(symbol, exchange)
        try:
            data = await self._get("profile", {"symbol": td_symbol})
        except Exception as exc:
            raise ExternalServiceError(f"Twelve Data profile failed for {td_symbol}: {exc}") from exc

        return CompanyProfileData(
            description=data.get("description"),
            ceo=data.get("CEO"),
            headquarters=", ".join(p for p in (data.get("address"), data.get("city"), data.get("country")) if p) or None,
            employees=int(data["employees"]) if data.get("employees") else None,
            website=data.get("website"),
            primary_exchange=data.get("exchange"),
            ipo_date=None,
            business_segments=[],
        )

    # ── Ratios / financials / earnings ──────────────────────────────────────
    # Twelve Data's free tier doesn't expose fundamentals at all (Grow-tier+
    # only). These raise so the composite provider's waterfall correctly
    # reports "unavailable" rather than silently returning empty data.

    async def get_ratios(self, symbol: str, exchange: str | None) -> RatiosData:
        raise ExternalServiceError("Twelve Data free tier does not support ratios/fundamentals")

    async def get_financial_statements(
        self, symbol: str, exchange: str | None, statement_type: str, period: str
    ) -> list[FinancialPeriod]:
        raise ExternalServiceError("Twelve Data free tier does not support financial statements")

    async def get_earnings(self, symbol: str, exchange: str | None) -> EarningsData:
        raise ExternalServiceError("Twelve Data free tier does not support earnings data")

    async def get_news(self, symbol: str, exchange: str | None, limit: int = 10) -> list[NewsArticle]:
        raise ExternalServiceError("Twelve Data free tier does not support news")

    async def get_analyst_insights(self, symbol: str, exchange: str | None) -> AnalystInsightsData:
        raise ExternalServiceError("Twelve Data free tier does not support analyst insights")
