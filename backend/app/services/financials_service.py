"""
Financials service — cache-through orchestration for ratios, financial
statements, and earnings. Same layering principle as market_data_service.py,
minus the Redis hot-path layer: this data only changes quarterly (statements,
earnings) or daily (ratios, since P/E depends on live price), so a Postgres
freshness check is enough — there's no meaningful "many requests per second"
hot path to protect against here the way there is for live quotes.
"""

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.financials import Earnings, FinancialStatement, Ratios
from app.providers.llm.base import LLMProvider
from app.providers.market_data.base import MarketDataProvider
from app.repositories.financials_repository import FinancialsRepository

logger = get_logger(__name__)

_FRESHNESS = timedelta(hours=20)
PROVIDER_SOURCE_NAME = "yfinance"


def _now() -> datetime:
    return datetime.utcnow()


class FinancialsService:

    def __init__(
        self,
        session: AsyncSession,
        provider: MarketDataProvider,
        llm: LLMProvider | None = None,
    ) -> None:
        self._session = session
        self._provider = provider
        self._repo = FinancialsRepository(session)
        self._llm = llm

    # ── Ratios ───────────────────────────────────────────────────────────────

    async def get_ratios(self, ticker_id: int, symbol: str, exchange: str | None) -> dict:
        existing = await self._repo.get_ratios(ticker_id)
        if existing and (_now() - existing.fetched_at) <= _FRESHNESS:
            return {**_ratios_row_to_dict(existing), "status": "cached"}

        try:
            data = await self._provider.get_ratios(symbol, exchange)
            row = await self._repo.upsert_ratios(ticker_id, data, source=PROVIDER_SOURCE_NAME, fetched_at=_now())
            await self._session.commit()
            return {**_ratios_row_to_dict(row), "status": "live"}
        except Exception as exc:
            logger.warning("Live ratios fetch failed, falling back", extra={"ticker_id": ticker_id, "error": str(exc)})
            if existing:
                return {**_ratios_row_to_dict(existing), "status": "cached"}
            return {"status": "unavailable"}

    # ── Financial statements ─────────────────────────────────────────────────

    async def get_statements(
        self, company_id: int, symbol: str, exchange: str | None, statement_type: str, period_type: str
    ) -> dict:
        existing = await self._repo.get_statements(company_id, statement_type, period_type)
        if existing and (_now() - existing[0].fetched_at) <= _FRESHNESS:
            return {"periods": [_statement_row_to_dict(r) for r in existing], "status": "cached"}

        try:
            periods = await self._provider.get_financial_statements(symbol, exchange, statement_type, period_type)
            if not periods:
                raise ValueError(f"No {statement_type}/{period_type} data returned")
            await self._repo.upsert_statements(
                company_id, statement_type, period_type, periods,
                source=PROVIDER_SOURCE_NAME, fetched_at=_now(),
            )
            await self._session.commit()
            rows = await self._repo.get_statements(company_id, statement_type, period_type)
            return {"periods": [_statement_row_to_dict(r) for r in rows], "status": "live"}
        except Exception as exc:
            logger.warning(
                "Live statement fetch failed, falling back",
                extra={"company_id": company_id, "statement": statement_type, "error": str(exc)},
            )
            if existing:
                return {"periods": [_statement_row_to_dict(r) for r in existing], "status": "cached"}
            return {"periods": [], "status": "unavailable"}

    # ── Earnings ─────────────────────────────────────────────────────────────

    async def get_earnings(self, company_id: int, symbol: str, exchange: str | None) -> dict:
        existing = await self._repo.get_earnings(company_id)
        if existing and (_now() - existing.fetched_at) <= _FRESHNESS:
            return {**_earnings_row_to_dict(existing), "status": "cached"}

        try:
            data = await self._provider.get_earnings(symbol, exchange)
            ai_summary = await self._generate_ai_summary(symbol, data)
            row = await self._repo.upsert_earnings(
                company_id, data, ai_summary, source=PROVIDER_SOURCE_NAME, fetched_at=_now()
            )
            await self._session.commit()
            return {**_earnings_row_to_dict(row), "status": "live"}
        except Exception as exc:
            logger.warning("Live earnings fetch failed, falling back", extra={"company_id": company_id, "error": str(exc)})
            if existing:
                return {**_earnings_row_to_dict(existing), "status": "cached"}
            return {"status": "unavailable"}

    async def _generate_ai_summary(self, symbol: str, data) -> str | None:
        """Reuse the platform's existing Ollama LLM to summarize the earnings
        surprise history — same free-LLM infra as the video analysis pipeline.
        Best-effort: a down/misconfigured LLM shouldn't block earnings data
        the way it doesn't block the AI-video bundle in company_intelligence_service."""
        if not self._llm or not data.history:
            return None
        try:
            lines = "\n".join(
                f"- {h.earnings_date.date()}: estimate {h.eps_estimate}, reported {h.eps_reported}, "
                f"surprise {h.surprise_pct}%"
                for h in data.history[:6]
            )
            response = await self._llm.complete(
                system_prompt=(
                    "You are a financial analyst. In 2-3 sentences, summarize this company's "
                    "recent earnings track record — whether it tends to beat or miss estimates, "
                    "and any trend in surprise magnitude. Be factual and concise, no filler."
                ),
                user_prompt=f"Earnings history for {symbol}:\n{lines}",
                temperature=0.2,
            )
            return response.content.strip()
        except Exception as exc:
            logger.info("AI earnings summary skipped", extra={"symbol": symbol, "error": str(exc)})
            return None


def _ratios_row_to_dict(row: Ratios) -> dict:
    return {
        "pe_trailing": _f(row.pe_trailing), "pe_forward": _f(row.pe_forward),
        "peg_ratio": _f(row.peg_ratio), "price_to_book": _f(row.price_to_book),
        "ev_to_ebitda": _f(row.ev_to_ebitda), "roe": _f(row.roe), "roa": _f(row.roa),
        "roic": _f(row.roic), "debt_to_equity": _f(row.debt_to_equity),
        "dividend_yield": _f(row.dividend_yield), "current_ratio": _f(row.current_ratio),
        "quick_ratio": _f(row.quick_ratio), "eps_trailing": _f(row.eps_trailing),
        "eps_forward": _f(row.eps_forward), "beta": _f(row.beta),
        "source": row.source, "fetched_at": row.fetched_at.isoformat(),
    }


def _statement_row_to_dict(row: FinancialStatement) -> dict:
    return {
        "period_end": row.period_end.isoformat(),
        "line_items": row.line_items,
    }


def _earnings_row_to_dict(row: Earnings) -> dict:
    return {
        "next_earnings_date": row.next_earnings_date.isoformat() if row.next_earnings_date else None,
        "eps_estimate_low": _f(row.eps_estimate_low), "eps_estimate_avg": _f(row.eps_estimate_avg),
        "eps_estimate_high": _f(row.eps_estimate_high),
        "revenue_estimate_low": _f(row.revenue_estimate_low), "revenue_estimate_avg": _f(row.revenue_estimate_avg),
        "revenue_estimate_high": _f(row.revenue_estimate_high),
        "history": row.history or [],
        "ai_summary": row.ai_summary,
        "source": row.source, "fetched_at": row.fetched_at.isoformat(),
    }


def _f(value) -> float | None:
    return float(value) if value is not None else None
