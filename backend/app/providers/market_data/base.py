"""
Market data provider interface.

All market data adapters (yfinance today, Twelve Data as fallback) implement
MarketDataProvider. Mirrors the LLMProvider/EmbeddingProvider port pattern in
app/providers/llm/base.py.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime

# Chart ranges the API accepts, mapped to provider-specific period strings
# by each concrete provider.
CHART_RANGES = ("1D", "1W", "1M", "3M", "6M", "1Y", "5Y", "MAX")


@dataclass
class SymbolMatch:
    """A candidate ticker returned from a symbol/company search."""
    symbol: str            # bare symbol, e.g. "RELIANCE" (no exchange suffix)
    exchange: str | None   # e.g. "NSE", "BSE", "NASDAQ", "NYSE"
    name: str = ""
    provider_symbol: str = ""  # the exact string the provider expects, e.g. "RELIANCE.NS"


@dataclass
class QuoteData:
    """A live/latest quote snapshot."""
    price: float | None = None
    change_abs: float | None = None
    change_pct: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    volume: int | None = None
    market_cap: float | None = None
    week52_high: float | None = None
    week52_low: float | None = None
    bid: float | None = None
    ask: float | None = None
    vwap: float | None = None
    pre_market_price: float | None = None
    after_hours_price: float | None = None
    currency: str | None = None


@dataclass
class OHLCVBar:
    """A single price bar for charting."""
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None


@dataclass
class CompanyProfileData:
    """Company overview / fundamentals metadata."""
    description: str | None = None
    ceo: str | None = None
    headquarters: str | None = None
    employees: int | None = None
    website: str | None = None
    primary_exchange: str | None = None
    ipo_date: date | None = None
    business_segments: list[str] = field(default_factory=list)


# Statement types accepted by get_financial_statements
STATEMENT_TYPES = ("income", "balance", "cashflow")
STATEMENT_PERIODS = ("annual", "quarterly")


@dataclass
class RatiosData:
    """Key financial ratios — almost all come straight from the provider's
    fundamentals feed; ROIC is the one exception that needs deriving from
    the raw financial statements (EBIT, tax rate, invested capital)."""
    pe_trailing: float | None = None
    pe_forward: float | None = None
    peg_ratio: float | None = None
    price_to_book: float | None = None
    ev_to_ebitda: float | None = None
    roe: float | None = None
    roa: float | None = None
    roic: float | None = None
    debt_to_equity: float | None = None
    dividend_yield: float | None = None
    current_ratio: float | None = None
    quick_ratio: float | None = None
    eps_trailing: float | None = None
    eps_forward: float | None = None
    beta: float | None = None


@dataclass
class FinancialPeriod:
    """One reporting period (a column) of a financial statement."""
    period_end: date
    line_items: dict[str, float | None]


@dataclass
class EarningsHistoryEntry:
    earnings_date: datetime
    eps_estimate: float | None
    eps_reported: float | None
    surprise_pct: float | None


@dataclass
class EarningsData:
    next_earnings_date: date | None = None
    eps_estimate_low: float | None = None
    eps_estimate_avg: float | None = None
    eps_estimate_high: float | None = None
    revenue_estimate_low: float | None = None
    revenue_estimate_avg: float | None = None
    revenue_estimate_high: float | None = None
    history: list[EarningsHistoryEntry] = field(default_factory=list)


@dataclass
class NewsArticle:
    """A news article — sentiment/impact_score/related_tickers are added
    later by news_service's AI classification pass, not by the provider."""
    title: str
    summary: str
    source: str
    url: str
    published_at: datetime
    thumbnail_url: str | None = None


@dataclass
class AnalystRecommendationPeriod:
    """Buy/hold/sell consensus counts for one month (0m = current, -1m = a
    month ago, etc.) — lets the caller see if consensus is shifting."""
    period: str
    strong_buy: int
    buy: int
    hold: int
    sell: int
    strong_sell: int


@dataclass
class AnalystAction:
    grade_date: datetime
    firm: str
    to_grade: str
    from_grade: str
    action: str
    current_price_target: float | None = None
    prior_price_target: float | None = None


@dataclass
class InstitutionalHolder:
    holder: str
    shares: int
    date_reported: date | None
    pct_held: float | None
    value: float | None
    pct_change: float | None


@dataclass
class InsiderTransaction:
    insider: str
    position: str | None
    text: str | None
    shares: int | None
    value: float | None
    start_date: date | None
    ownership: str | None


@dataclass
class AnalystInsightsData:
    recommendation_mean: float | None = None
    recommendation_key: str | None = None
    target_mean: float | None = None
    target_high: float | None = None
    target_low: float | None = None
    target_median: float | None = None
    num_analyst_opinions: int | None = None
    held_pct_institutions: float | None = None
    held_pct_insiders: float | None = None
    recommendation_trend: list[AnalystRecommendationPeriod] = field(default_factory=list)
    actions: list[AnalystAction] = field(default_factory=list)
    institutional_holders: list[InstitutionalHolder] = field(default_factory=list)
    insider_transactions: list[InsiderTransaction] = field(default_factory=list)


class MarketDataProvider(ABC):
    """Port for live market data, history, profiles, and symbol resolution."""

    @abstractmethod
    async def search_symbol(self, query: str) -> list[SymbolMatch]:
        """Resolve a free-text query (ticker, company name, or keyword) to candidates."""

    @abstractmethod
    async def get_quote(self, symbol: str, exchange: str | None) -> QuoteData:
        """Fetch the latest quote snapshot for a resolved symbol."""

    @abstractmethod
    async def get_history(
        self,
        symbol: str,
        exchange: str | None,
        chart_range: str,
        interval: str | None = None,
    ) -> list[OHLCVBar]:
        """Fetch OHLCV bars for the given range. chart_range must be one of CHART_RANGES."""

    @abstractmethod
    async def get_profile(self, symbol: str, exchange: str | None) -> CompanyProfileData:
        """Fetch company overview metadata for a resolved symbol."""

    @abstractmethod
    async def get_ratios(self, symbol: str, exchange: str | None) -> RatiosData:
        """Fetch key financial ratios for a resolved symbol."""

    @abstractmethod
    async def get_financial_statements(
        self, symbol: str, exchange: str | None, statement_type: str, period: str
    ) -> list[FinancialPeriod]:
        """Fetch a curated set of line items for one statement type/period.
        statement_type must be one of STATEMENT_TYPES, period one of STATEMENT_PERIODS."""

    @abstractmethod
    async def get_earnings(self, symbol: str, exchange: str | None) -> EarningsData:
        """Fetch next earnings date/estimates and recent earnings surprise history."""

    @abstractmethod
    async def get_news(self, symbol: str, exchange: str | None, limit: int = 10) -> list[NewsArticle]:
        """Fetch recent news articles. Sentiment/impact scoring is added later
        by news_service, not by the provider."""

    @abstractmethod
    async def get_analyst_insights(self, symbol: str, exchange: str | None) -> AnalystInsightsData:
        """Fetch analyst consensus, price targets, upgrades/downgrades,
        institutional ownership, and insider transactions."""
