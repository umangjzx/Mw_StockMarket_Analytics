"""
Company/ticker resolution repository for the Company Intelligence module.

Deliberately separate from the entity-extraction upsert logic in
analysis_service.py, which matches companies by exact name string and is
known to produce duplicates (e.g. "Meta" vs "Meta Platforms Inc.").
Resolution here matches by (symbol, exchange) first — a stable key — so this
module doesn't inherit that problem.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.company import Company, Ticker
from app.providers.market_data.base import SymbolMatch


class CompanyRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_ticker_by_symbol(self, symbol: str, exchange: str | None = None) -> Ticker | None:
        query = select(Ticker).options(selectinload(Ticker.company)).where(
            Ticker.symbol == symbol.upper()
        )
        if exchange:
            query = query.where(Ticker.exchange == exchange)
        result = await self._session.execute(query.limit(1))
        return result.scalars().first()

    async def search_companies_by_name(self, name_query: str, limit: int = 10) -> list[Company]:
        result = await self._session.execute(
            select(Company)
            .options(selectinload(Company.tickers))
            .where(Company.name.ilike(f"%{name_query}%"))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_or_create_by_resolved_symbol(self, match: SymbolMatch) -> Ticker:
        """
        Ensure a local Ticker (and its Company) exists for a provider-resolved
        symbol, so future lookups for the same ticker are served locally.
        """
        existing = await self.get_ticker_by_symbol(match.symbol, match.exchange)
        if existing:
            return existing

        company: Company | None = None
        if match.name:
            result = await self._session.execute(
                select(Company).where(Company.name == match.name)
            )
            company = result.scalar_one_or_none()

        if not company:
            company = Company(name=match.name or match.symbol)
            self._session.add(company)
            await self._session.flush()

        ticker = Ticker(
            symbol=match.symbol.upper(),
            exchange=match.exchange,
            company_id=company.id,
        )
        self._session.add(ticker)
        await self._session.flush()
        # Re-fetch with the relationship eagerly loaded rather than relying on
        # session.refresh() for relationship attributes.
        return await self.get_ticker_by_symbol(ticker.symbol, ticker.exchange)
