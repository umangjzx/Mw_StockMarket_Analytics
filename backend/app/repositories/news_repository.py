"""
News repository — CRUD + dedup for news_articles.

Note the aliasing below: app.providers.market_data.base.NewsArticle is the
plain dataclass a provider returns; app.models.news_analyst.NewsArticle is
the ORM row. Both are legitimately named "NewsArticle" in their own module —
this file is the one place that needs both at once.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.news_analyst import NewsArticle as NewsArticleRow
from app.providers.market_data.base import NewsArticle as NewsArticleData


class NewsRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_articles(self, company_id: int, limit: int = 20) -> list[NewsArticleRow]:
        result = await self._session.execute(
            select(NewsArticleRow)
            .where(NewsArticleRow.company_id == company_id)
            .order_by(NewsArticleRow.published_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def upsert_articles(
        self, company_id: int, articles: list[NewsArticleData], fetched_at: datetime
    ) -> int:
        """Insert new articles, skip ones already seen for this company (by
        URL) — an existing row's AI classification is never overwritten by a
        re-fetch of the same article."""
        if not articles:
            return 0

        rows = [
            {
                "company_id": company_id,
                "title": a.title,
                "summary": a.summary,
                "source": a.source,
                "url": a.url,
                "published_at": a.published_at,
                "thumbnail_url": a.thumbnail_url,
                "fetched_at": fetched_at,
            }
            for a in articles
        ]

        stmt = pg_insert(NewsArticleRow).values(rows)
        stmt = stmt.on_conflict_do_nothing(constraint="uq_news_articles_company_url")
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount or 0

    async def get_unclassified(self, company_id: int) -> list[NewsArticleRow]:
        result = await self._session.execute(
            select(NewsArticleRow).where(
                NewsArticleRow.company_id == company_id,
                NewsArticleRow.sentiment.is_(None),
            )
        )
        return list(result.scalars().all())

    async def apply_classification(
        self, article_id: int, sentiment: str, impact_score: float, related_tickers: list[str]
    ) -> None:
        result = await self._session.execute(
            select(NewsArticleRow).where(NewsArticleRow.id == article_id)
        )
        row = result.scalar_one_or_none()
        if row:
            row.sentiment = sentiment
            row.impact_score = impact_score
            row.related_tickers = related_tickers
            await self._session.flush()
