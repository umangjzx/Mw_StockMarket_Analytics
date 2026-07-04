"""
yfinance market data provider — FREE, no API key.

Covers US exchanges natively and Indian exchanges via Yahoo's suffix
convention (RELIANCE.NS for NSE, RELIANCE.BO for BSE). yfinance is a
synchronous library under the hood (uses `requests`), so every call here
runs in a worker thread via asyncio.to_thread to avoid blocking the event
loop — the same constraint that makes create_worker_session() necessary for
Celery tasks elsewhere in this codebase.
"""

import asyncio
from datetime import date, datetime, timezone

import yfinance as yf

from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.providers.market_data.base import (
    AnalystAction,
    AnalystInsightsData,
    AnalystRecommendationPeriod,
    CompanyProfileData,
    EarningsData,
    EarningsHistoryEntry,
    FinancialPeriod,
    InsiderTransaction,
    InstitutionalHolder,
    MarketDataProvider,
    NewsArticle,
    OHLCVBar,
    QuoteData,
    RatiosData,
    SymbolMatch,
)

logger = get_logger(__name__)

_EXCHANGE_SUFFIX = {"NSE": ".NS", "BSE": ".BO"}

# Chart range -> (yfinance period, default interval when caller doesn't specify one)
_RANGE_MAP: dict[str, tuple[str, str]] = {
    "1D": ("1d", "5m"),
    "1W": ("5d", "30m"),
    "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"),
    "6M": ("6mo", "1d"),
    "1Y": ("1y", "1d"),
    "5Y": ("5y", "1wk"),
    "MAX": ("max", "1mo"),
}


def _to_yf_symbol(symbol: str, exchange: str | None) -> str:
    if "." in symbol:
        return symbol  # already provider-qualified, e.g. "RELIANCE.NS"
    # Substring match, not exact — some existing ticker rows (populated by the
    # video-analysis pipeline, not this module) store combined exchange
    # strings like "NSE|BSE". NSE takes priority when both are present.
    exch = (exchange or "").upper()
    for code, suffix in _EXCHANGE_SUFFIX.items():
        if code in exch:
            return f"{symbol.upper()}{suffix}"
    return symbol.upper()


def _split_yf_symbol(yf_symbol: str) -> tuple[str, str | None]:
    if yf_symbol.upper().endswith(".NS"):
        return yf_symbol[:-3], "NSE"
    if yf_symbol.upper().endswith(".BO"):
        return yf_symbol[:-3], "BSE"
    return yf_symbol, None


class YFinanceProvider(MarketDataProvider):

    async def search_symbol(self, query: str) -> list[SymbolMatch]:
        query = query.strip()
        if not query:
            return []

        matches: list[SymbolMatch] = []

        # 1. Yahoo's own fuzzy search (handles company names and keywords well)
        try:
            results = await asyncio.to_thread(self._search_via_yf_search, query)
            matches.extend(results)
        except Exception as exc:
            logger.warning("yfinance Search failed", extra={"query": query, "error": str(exc)})

        # 2. If the query looks like a bare ticker, also probe common suffixes
        # directly — Yahoo's fuzzy search sometimes misses exact Indian symbols.
        if query.isalnum() and not any(m.provider_symbol.split(".")[0] == query.upper() for m in matches):
            for candidate in (query.upper(), f"{query.upper()}.NS", f"{query.upper()}.BO"):
                try:
                    probe = await asyncio.to_thread(self._probe_symbol, candidate)
                    if probe:
                        matches.append(probe)
                except Exception:
                    continue

        # De-duplicate by provider_symbol, preserving first-seen order
        seen: set[str] = set()
        deduped = []
        for m in matches:
            if m.provider_symbol not in seen:
                seen.add(m.provider_symbol)
                deduped.append(m)
        return deduped

    def _search_via_yf_search(self, query: str) -> list[SymbolMatch]:
        searcher = yf.Search(query, max_results=8)
        out = []
        for quote in getattr(searcher, "quotes", []) or []:
            symbol = quote.get("symbol")
            if not symbol:
                continue
            bare, exchange = _split_yf_symbol(symbol)
            out.append(SymbolMatch(
                symbol=bare,
                exchange=exchange or quote.get("exchange"),
                name=quote.get("shortname") or quote.get("longname") or "",
                provider_symbol=symbol,
            ))
        return out

    def _probe_symbol(self, yf_symbol: str) -> SymbolMatch | None:
        """Confirm a candidate symbol actually resolves to real data."""
        ticker = yf.Ticker(yf_symbol)
        info = ticker.fast_info
        if not info or info.get("lastPrice") in (None, 0):
            return None
        bare, exchange = _split_yf_symbol(yf_symbol)
        name = ""
        try:
            name = ticker.info.get("shortName", "") or ticker.info.get("longName", "")
        except Exception:
            pass
        return SymbolMatch(symbol=bare, exchange=exchange, name=name, provider_symbol=yf_symbol)

    async def get_quote(self, symbol: str, exchange: str | None) -> QuoteData:
        yf_symbol = _to_yf_symbol(symbol, exchange)
        try:
            return await asyncio.to_thread(self._fetch_quote_sync, yf_symbol)
        except Exception as exc:
            raise ExternalServiceError(f"yfinance quote failed for {yf_symbol}: {exc}") from exc

    def _fetch_quote_sync(self, yf_symbol: str) -> QuoteData:
        ticker = yf.Ticker(yf_symbol)
        fi = ticker.fast_info
        if not fi or fi.get("lastPrice") in (None, 0):
            raise ValueError(f"No live data for {yf_symbol}")

        price = fi.get("lastPrice")
        prev_close = fi.get("previousClose")
        change_abs = (price - prev_close) if (price is not None and prev_close is not None) else None
        change_pct = (
            (change_abs / prev_close * 100) if (change_abs is not None and prev_close) else None
        )

        quote = QuoteData(
            price=price,
            change_abs=change_abs,
            change_pct=change_pct,
            open=fi.get("open"),
            high=fi.get("dayHigh"),
            low=fi.get("dayLow"),
            prev_close=prev_close,
            volume=fi.get("lastVolume"),
            market_cap=fi.get("marketCap"),
            week52_high=fi.get("yearHigh"),
            week52_low=fi.get("yearLow"),
            currency=fi.get("currency"),
        )

        # Bid/ask/VWAP/pre-post-market are only in the heavier `.info` scrape,
        # which is slower and occasionally rate-limited — best-effort only.
        try:
            info = ticker.info
            quote.bid = info.get("bid")
            quote.ask = info.get("ask")
            quote.vwap = info.get("vwap")
            quote.pre_market_price = info.get("preMarketPrice")
            quote.after_hours_price = info.get("postMarketPrice")
        except Exception as exc:
            logger.info("yfinance .info enrichment skipped", extra={"symbol": yf_symbol, "error": str(exc)})

        return quote

    async def get_history(
        self,
        symbol: str,
        exchange: str | None,
        chart_range: str,
        interval: str | None = None,
    ) -> list[OHLCVBar]:
        if chart_range not in _RANGE_MAP:
            raise ValueError(f"Unsupported chart range: {chart_range}")
        yf_symbol = _to_yf_symbol(symbol, exchange)
        period, default_interval = _RANGE_MAP[chart_range]
        resolved_interval = interval or default_interval
        try:
            return await asyncio.to_thread(
                self._fetch_history_sync, yf_symbol, period, resolved_interval
            )
        except Exception as exc:
            raise ExternalServiceError(
                f"yfinance history failed for {yf_symbol} ({period}/{resolved_interval}): {exc}"
            ) from exc

    def _fetch_history_sync(self, yf_symbol: str, period: str, interval: str) -> list[OHLCVBar]:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period, interval=interval, auto_adjust=False)
        bars = []
        for ts, row in df.iterrows():
            py_ts = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            # yfinance returns bar timestamps localized to the exchange's own
            # timezone (e.g. Asia/Kolkata for NSE) — this project's DB columns
            # are naive UTC, so convert rather than strip blindly.
            if py_ts.tzinfo is not None:
                py_ts = py_ts.astimezone(timezone.utc).replace(tzinfo=None)
            bars.append(OHLCVBar(
                ts=py_ts,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]) if row.get("Volume") is not None else None,
            ))
        return bars

    async def get_profile(self, symbol: str, exchange: str | None) -> CompanyProfileData:
        yf_symbol = _to_yf_symbol(symbol, exchange)
        try:
            return await asyncio.to_thread(self._fetch_profile_sync, yf_symbol)
        except Exception as exc:
            raise ExternalServiceError(f"yfinance profile failed for {yf_symbol}: {exc}") from exc

    def _fetch_profile_sync(self, yf_symbol: str) -> CompanyProfileData:
        info = yf.Ticker(yf_symbol).info
        if not info:
            raise ValueError(f"No profile data for {yf_symbol}")

        ceo = None
        for officer in info.get("companyOfficers", []) or []:
            title = (officer.get("title") or "").lower()
            if "chief executive" in title or title == "ceo":
                ceo = officer.get("name")
                break

        hq_parts = [info.get("city"), info.get("state"), info.get("country")]
        headquarters = ", ".join(p for p in hq_parts if p) or None

        ipo_date = None
        first_trade_ms = info.get("firstTradeDateEpochUtc") or info.get("firstTradeDateMilliseconds")
        if first_trade_ms:
            try:
                # yfinance mixes seconds and milliseconds across fields/versions
                seconds = first_trade_ms / 1000 if first_trade_ms > 10_000_000_000 else first_trade_ms
                ipo_date = datetime.utcfromtimestamp(seconds).date()
            except (ValueError, OSError, OverflowError):
                ipo_date = None

        return CompanyProfileData(
            description=info.get("longBusinessSummary"),
            ceo=ceo,
            headquarters=headquarters,
            employees=info.get("fullTimeEmployees"),
            website=info.get("website"),
            primary_exchange=info.get("exchange") or info.get("fullExchangeName"),
            ipo_date=ipo_date,
            business_segments=[],  # not reliably exposed by yfinance — best-effort empty for now
        )

    # ── Ratios ───────────────────────────────────────────────────────────────

    async def get_ratios(self, symbol: str, exchange: str | None) -> RatiosData:
        yf_symbol = _to_yf_symbol(symbol, exchange)
        try:
            return await asyncio.to_thread(self._fetch_ratios_sync, yf_symbol)
        except Exception as exc:
            raise ExternalServiceError(f"yfinance ratios failed for {yf_symbol}: {exc}") from exc

    def _fetch_ratios_sync(self, yf_symbol: str) -> RatiosData:
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info
        if not info:
            raise ValueError(f"No ratios data for {yf_symbol}")

        return RatiosData(
            pe_trailing=info.get("trailingPE"),
            pe_forward=info.get("forwardPE"),
            peg_ratio=info.get("pegRatio"),
            price_to_book=info.get("priceToBook"),
            ev_to_ebitda=info.get("enterpriseToEbitda"),
            roe=info.get("returnOnEquity"),
            roa=info.get("returnOnAssets"),
            roic=self._compute_roic(ticker),
            debt_to_equity=info.get("debtToEquity"),
            dividend_yield=info.get("dividendYield"),
            current_ratio=info.get("currentRatio"),
            quick_ratio=info.get("quickRatio"),
            eps_trailing=info.get("trailingEps"),
            eps_forward=info.get("forwardEps"),
            beta=info.get("beta"),
        )

    def _compute_roic(self, ticker: "yf.Ticker") -> float | None:
        """ROIC = NOPAT / Invested Capital. Not exposed directly by yfinance —
        derive it from the latest annual EBIT/tax rate and the most recent
        (quarterly, if available) invested capital figure."""
        try:
            income = ticker.income_stmt
            if income is None or income.empty:
                return None
            latest_col = income.columns[0]
            ebit = income.loc["EBIT", latest_col] if "EBIT" in income.index else None
            tax_rate = income.loc["Tax Rate For Calcs", latest_col] if "Tax Rate For Calcs" in income.index else None
            if ebit is None or tax_rate is None:
                return None

            balance = ticker.quarterly_balance_sheet
            if balance is None or balance.empty or "Invested Capital" not in balance.index:
                balance = ticker.balance_sheet
            if balance is None or balance.empty or "Invested Capital" not in balance.index:
                return None
            invested_capital = balance.loc["Invested Capital", balance.columns[0]]
            if not invested_capital:
                return None

            nopat = float(ebit) * (1 - float(tax_rate))
            return nopat / float(invested_capital)
        except Exception as exc:
            logger.info("ROIC computation skipped", extra={"error": str(exc)})
            return None

    # ── Financial statements ─────────────────────────────────────────────────

    _CURATED_LINE_ITEMS = {
        "income": [
            "Total Revenue", "Cost Of Revenue", "Gross Profit", "Operating Expense",
            "Operating Income", "EBITDA", "EBIT", "Net Income", "Diluted EPS",
            "Basic EPS", "Tax Rate For Calcs",
        ],
        "balance": [
            "Total Assets", "Total Liabilities Net Minority Interest", "Total Debt",
            "Current Assets", "Current Liabilities", "Stockholders Equity",
            "Cash And Cash Equivalents", "Working Capital", "Invested Capital", "Net Debt",
        ],
        "cashflow": [
            "Operating Cash Flow", "Capital Expenditure", "Free Cash Flow",
            "Cash Dividends Paid", "Repurchase Of Capital Stock", "Depreciation And Amortization",
        ],
    }
    _STATEMENT_ATTR = {
        ("income", "annual"): "income_stmt",
        ("income", "quarterly"): "quarterly_income_stmt",
        ("balance", "annual"): "balance_sheet",
        ("balance", "quarterly"): "quarterly_balance_sheet",
        ("cashflow", "annual"): "cashflow",
        ("cashflow", "quarterly"): "quarterly_cashflow",
    }

    async def get_financial_statements(
        self, symbol: str, exchange: str | None, statement_type: str, period: str
    ) -> list[FinancialPeriod]:
        yf_symbol = _to_yf_symbol(symbol, exchange)
        try:
            return await asyncio.to_thread(
                self._fetch_statement_sync, yf_symbol, statement_type, period
            )
        except Exception as exc:
            raise ExternalServiceError(
                f"yfinance {statement_type}/{period} statement failed for {yf_symbol}: {exc}"
            ) from exc

    def _fetch_statement_sync(
        self, yf_symbol: str, statement_type: str, period: str
    ) -> list[FinancialPeriod]:
        attr = self._STATEMENT_ATTR[(statement_type, period)]
        df = getattr(yf.Ticker(yf_symbol), attr)
        if df is None or df.empty:
            return []

        wanted = self._CURATED_LINE_ITEMS[statement_type]
        periods = []
        for col in df.columns:
            line_items = {}
            for item in wanted:
                if item in df.index:
                    val = df.loc[item, col]
                    line_items[item] = float(val) if val is not None and val == val else None  # NaN check
            periods.append(FinancialPeriod(
                period_end=col.date() if hasattr(col, "date") else col,
                line_items=line_items,
            ))
        return periods

    # ── Earnings ─────────────────────────────────────────────────────────────

    async def get_earnings(self, symbol: str, exchange: str | None) -> EarningsData:
        yf_symbol = _to_yf_symbol(symbol, exchange)
        try:
            return await asyncio.to_thread(self._fetch_earnings_sync, yf_symbol)
        except Exception as exc:
            raise ExternalServiceError(f"yfinance earnings failed for {yf_symbol}: {exc}") from exc

    def _fetch_earnings_sync(self, yf_symbol: str) -> EarningsData:
        ticker = yf.Ticker(yf_symbol)
        calendar = ticker.calendar or {}

        next_dates = calendar.get("Earnings Date") or []
        next_earnings_date = next_dates[0] if next_dates else None

        data = EarningsData(
            next_earnings_date=next_earnings_date,
            eps_estimate_low=calendar.get("Earnings Low"),
            eps_estimate_avg=calendar.get("Earnings Average"),
            eps_estimate_high=calendar.get("Earnings High"),
            revenue_estimate_low=calendar.get("Revenue Low"),
            revenue_estimate_avg=calendar.get("Revenue Average"),
            revenue_estimate_high=calendar.get("Revenue High"),
        )

        try:
            history_df = ticker.get_earnings_dates(limit=8)
        except Exception as exc:
            logger.info("Earnings history unavailable", extra={"symbol": yf_symbol, "error": str(exc)})
            return data

        if history_df is None or history_df.empty:
            return data

        for ts, row in history_df.iterrows():
            py_ts = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            if py_ts.tzinfo is not None:
                py_ts = py_ts.astimezone(timezone.utc).replace(tzinfo=None)

            def _clean(v):
                return float(v) if v is not None and v == v else None  # NaN check

            data.history.append(EarningsHistoryEntry(
                earnings_date=py_ts,
                eps_estimate=_clean(row.get("EPS Estimate")),
                eps_reported=_clean(row.get("Reported EPS")),
                surprise_pct=_clean(row.get("Surprise(%)")),
            ))
        return data

    # ── News ─────────────────────────────────────────────────────────────────

    async def get_news(self, symbol: str, exchange: str | None, limit: int = 10) -> list[NewsArticle]:
        yf_symbol = _to_yf_symbol(symbol, exchange)
        try:
            return await asyncio.to_thread(self._fetch_news_sync, yf_symbol, limit)
        except Exception as exc:
            raise ExternalServiceError(f"yfinance news failed for {yf_symbol}: {exc}") from exc

    def _fetch_news_sync(self, yf_symbol: str, limit: int) -> list[NewsArticle]:
        raw = yf.Ticker(yf_symbol).news or []
        articles = []
        for item in raw[:limit]:
            content = item.get("content", {})
            title = content.get("title")
            url = (content.get("canonicalUrl") or {}).get("url") or (content.get("clickThroughUrl") or {}).get("url")
            if not title or not url:
                continue

            pub_date_str = content.get("pubDate")
            published_at = _parse_iso_z(pub_date_str) or datetime.utcnow()

            articles.append(NewsArticle(
                title=title,
                summary=content.get("summary") or content.get("description") or "",
                source=(content.get("provider") or {}).get("displayName", "Unknown"),
                url=url,
                published_at=published_at,
                thumbnail_url=((content.get("thumbnail") or {}).get("originalUrl")),
            ))
        return articles

    # ── Analyst insights ─────────────────────────────────────────────────────

    async def get_analyst_insights(self, symbol: str, exchange: str | None) -> AnalystInsightsData:
        yf_symbol = _to_yf_symbol(symbol, exchange)
        try:
            return await asyncio.to_thread(self._fetch_analyst_insights_sync, yf_symbol)
        except Exception as exc:
            raise ExternalServiceError(f"yfinance analyst insights failed for {yf_symbol}: {exc}") from exc

    def _fetch_analyst_insights_sync(self, yf_symbol: str) -> AnalystInsightsData:
        ticker = yf.Ticker(yf_symbol)
        info = ticker.info or {}

        data = AnalystInsightsData(
            recommendation_mean=info.get("recommendationMean"),
            recommendation_key=info.get("recommendationKey"),
            target_mean=info.get("targetMeanPrice"),
            target_high=info.get("targetHighPrice"),
            target_low=info.get("targetLowPrice"),
            target_median=info.get("targetMedianPrice"),
            num_analyst_opinions=info.get("numberOfAnalystOpinions"),
            held_pct_institutions=info.get("heldPercentInstitutions"),
            held_pct_insiders=info.get("heldPercentInsiders"),
        )

        try:
            rec = ticker.recommendations
            if rec is not None and not rec.empty:
                for _, row in rec.iterrows():
                    data.recommendation_trend.append(AnalystRecommendationPeriod(
                        period=str(row.get("period")),
                        strong_buy=int(row.get("strongBuy", 0)),
                        buy=int(row.get("buy", 0)),
                        hold=int(row.get("hold", 0)),
                        sell=int(row.get("sell", 0)),
                        strong_sell=int(row.get("strongSell", 0)),
                    ))
        except Exception as exc:
            logger.info("Recommendation trend unavailable", extra={"symbol": yf_symbol, "error": str(exc)})

        try:
            actions = ticker.upgrades_downgrades
            if actions is not None and not actions.empty:
                for grade_date, row in actions.head(15).iterrows():
                    py_ts = grade_date.to_pydatetime() if hasattr(grade_date, "to_pydatetime") else grade_date
                    if py_ts.tzinfo is not None:
                        py_ts = py_ts.astimezone(timezone.utc).replace(tzinfo=None)
                    data.actions.append(AnalystAction(
                        grade_date=py_ts,
                        firm=str(row.get("Firm", "")),
                        to_grade=str(row.get("ToGrade", "")),
                        from_grade=str(row.get("FromGrade", "")),
                        action=str(row.get("Action", "")),
                        current_price_target=_nan_safe(row.get("currentPriceTarget")),
                        prior_price_target=_nan_safe(row.get("priorPriceTarget")),
                    ))
        except Exception as exc:
            logger.info("Upgrades/downgrades unavailable", extra={"symbol": yf_symbol, "error": str(exc)})

        try:
            holders = ticker.institutional_holders
            if holders is not None and not holders.empty:
                for _, row in holders.head(10).iterrows():
                    reported = row.get("Date Reported")
                    data.institutional_holders.append(InstitutionalHolder(
                        holder=str(row.get("Holder", "")),
                        shares=int(row.get("Shares", 0)),
                        date_reported=reported.date() if hasattr(reported, "date") else None,
                        pct_held=_nan_safe(row.get("pctHeld")),
                        value=_nan_safe(row.get("Value")),
                        pct_change=_nan_safe(row.get("pctChange")),
                    ))
        except Exception as exc:
            logger.info("Institutional holders unavailable", extra={"symbol": yf_symbol, "error": str(exc)})

        try:
            insiders = ticker.insider_transactions
            if insiders is not None and not insiders.empty:
                for _, row in insiders.head(10).iterrows():
                    start = row.get("Start Date")
                    data.insider_transactions.append(InsiderTransaction(
                        insider=str(row.get("Insider", "")),
                        position=row.get("Position") or None,
                        text=row.get("Text") or None,
                        shares=int(row["Shares"]) if row.get("Shares") == row.get("Shares") else None,
                        value=_nan_safe(row.get("Value")),
                        start_date=start.date() if hasattr(start, "date") else None,
                        ownership=row.get("Ownership") or None,
                    ))
        except Exception as exc:
            logger.info("Insider transactions unavailable", extra={"symbol": yf_symbol, "error": str(exc)})

        return data


def _nan_safe(value) -> float | None:
    return float(value) if value is not None and value == value else None  # NaN check


def _parse_iso_z(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        return None
