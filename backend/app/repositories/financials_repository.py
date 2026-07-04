"""
Financials repository — CRUD for financial_statements, ratios, and earnings.
Mirrors the shape of market_data_repository.py from Phase 1.
"""

from dataclasses import asdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financials import Earnings, FinancialStatement, Ratios
from app.providers.market_data.base import EarningsData, FinancialPeriod, RatiosData


class FinancialsRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Ratios ───────────────────────────────────────────────────────────────

    async def get_ratios(self, ticker_id: int) -> Ratios | None:
        result = await self._session.execute(
            select(Ratios).where(Ratios.ticker_id == ticker_id)
        )
        return result.scalar_one_or_none()

    async def upsert_ratios(
        self, ticker_id: int, data: RatiosData, source: str, fetched_at: datetime
    ) -> Ratios:
        existing = await self.get_ratios(ticker_id)
        fields = dict(
            pe_trailing=data.pe_trailing, pe_forward=data.pe_forward, peg_ratio=data.peg_ratio,
            price_to_book=data.price_to_book, ev_to_ebitda=data.ev_to_ebitda,
            roe=data.roe, roa=data.roa, roic=data.roic, debt_to_equity=data.debt_to_equity,
            dividend_yield=data.dividend_yield, current_ratio=data.current_ratio,
            quick_ratio=data.quick_ratio, eps_trailing=data.eps_trailing,
            eps_forward=data.eps_forward, beta=data.beta,
            source=source, fetched_at=fetched_at,
        )
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            await self._session.flush()
            return existing

        row = Ratios(ticker_id=ticker_id, **fields)
        self._session.add(row)
        await self._session.flush()
        return row

    # ── Financial statements ─────────────────────────────────────────────────

    async def get_statements(
        self, company_id: int, statement_type: str, period_type: str
    ) -> list[FinancialStatement]:
        result = await self._session.execute(
            select(FinancialStatement)
            .where(
                FinancialStatement.company_id == company_id,
                FinancialStatement.statement_type == statement_type,
                FinancialStatement.period_type == period_type,
            )
            .order_by(FinancialStatement.period_end.desc())
        )
        return list(result.scalars().all())

    async def upsert_statements(
        self,
        company_id: int,
        statement_type: str,
        period_type: str,
        periods: list[FinancialPeriod],
        source: str,
        fetched_at: datetime,
    ) -> int:
        if not periods:
            return 0

        rows = [
            {
                "company_id": company_id,
                "statement_type": statement_type,
                "period_type": period_type,
                "period_end": p.period_end,
                "line_items": p.line_items,
                "source": source,
                "fetched_at": fetched_at,
            }
            for p in periods
        ]

        stmt = pg_insert(FinancialStatement).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_financial_statements_period",
            set_={
                "line_items": stmt.excluded.line_items,
                "source": stmt.excluded.source,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return len(rows)

    # ── Earnings ─────────────────────────────────────────────────────────────

    async def get_earnings(self, company_id: int) -> Earnings | None:
        result = await self._session.execute(
            select(Earnings).where(Earnings.company_id == company_id)
        )
        return result.scalar_one_or_none()

    async def upsert_earnings(
        self,
        company_id: int,
        data: EarningsData,
        ai_summary: str | None,
        source: str,
        fetched_at: datetime,
    ) -> Earnings:
        existing = await self.get_earnings(company_id)
        fields = dict(
            next_earnings_date=data.next_earnings_date,
            eps_estimate_low=data.eps_estimate_low,
            eps_estimate_avg=data.eps_estimate_avg,
            eps_estimate_high=data.eps_estimate_high,
            revenue_estimate_low=data.revenue_estimate_low,
            revenue_estimate_avg=data.revenue_estimate_avg,
            revenue_estimate_high=data.revenue_estimate_high,
            history=[
                {**asdict(h), "earnings_date": h.earnings_date.isoformat()}
                for h in data.history
            ],
            ai_summary=ai_summary,
            source=source,
            fetched_at=fetched_at,
        )
        if existing:
            for key, value in fields.items():
                setattr(existing, key, value)
            await self._session.flush()
            return existing

        row = Earnings(company_id=company_id, **fields)
        self._session.add(row)
        await self._session.flush()
        return row
