"""
News service — fetches recent articles, dedupes by URL, and batch-classifies
sentiment/impact_score/related_tickers with a single Ollama call per refresh
(not one call per article — matches the platform's existing pattern of
batching LLM work, same principle as embedding_service.py's batched embeds).
"""

import json
import re
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.news_analyst import NewsArticle
from app.providers.llm.base import LLMProvider
from app.providers.market_data.base import MarketDataProvider
from app.prompts import news_classification as p
from app.repositories.news_repository import NewsRepository

logger = get_logger(__name__)

_REFRESH_INTERVAL = timedelta(hours=2)  # news is time-sensitive, refresh more often than fundamentals
PROVIDER_SOURCE_NAME = "yfinance"


def _now() -> datetime:
    return datetime.utcnow()


def _parse_json(raw: str) -> dict:
    text = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    return json.loads(text)


class NewsService:

    def __init__(
        self, session: AsyncSession, provider: MarketDataProvider, llm: LLMProvider | None = None
    ) -> None:
        self._session = session
        self._provider = provider
        self._repo = NewsRepository(session)
        self._llm = llm

    async def get_news(
        self, company_id: int, symbol: str, exchange: str | None, company_name: str, limit: int = 10
    ) -> dict:
        rows = await self._repo.get_articles(company_id, limit=limit)
        needs_refresh = not rows or (_now() - max(r.fetched_at for r in rows)) > _REFRESH_INTERVAL

        if needs_refresh:
            try:
                articles = await self._provider.get_news(symbol, exchange, limit)
                await self._repo.upsert_articles(company_id, articles, fetched_at=_now())
                await self._session.commit()
            except Exception as exc:
                logger.warning(
                    "Live news fetch failed, using whatever's already stored",
                    extra={"company_id": company_id, "symbol": symbol, "error": str(exc)},
                )

        # AI classification is independent of whether the fetch above
        # succeeded — there may be older unclassified articles either way,
        # and a down LLM shouldn't block the raw article list from returning.
        unclassified = await self._repo.get_unclassified(company_id)
        if unclassified:
            await self._classify_articles(unclassified, symbol, company_name)

        rows = await self._repo.get_articles(company_id, limit=limit)
        if not rows:
            return {"articles": [], "status": "unavailable"}
        status = "live" if needs_refresh else "cached"
        return {"articles": [_article_row_to_dict(r) for r in rows], "status": status}

    async def _classify_articles(self, articles: list[NewsArticle], symbol: str, company_name: str) -> None:
        if not self._llm:
            return
        try:
            texts = [f"{a.title} — {a.summary[:200]}" for a in articles]
            response = await self._llm.complete(
                system_prompt=p.SYSTEM,
                user_prompt=p.build_user_prompt(symbol, company_name, texts),
                response_format="json_object",
            )
            data = _parse_json(response.content)
            classifications = data.get("articles", [])

            for article, classification in zip(articles, classifications):
                await self._repo.apply_classification(
                    article.id,
                    sentiment=classification.get("sentiment", "neutral"),
                    impact_score=float(classification.get("impact_score", 0) or 0),
                    related_tickers=classification.get("related_tickers", []) or [],
                )
            await self._session.commit()
        except Exception as exc:
            logger.warning(
                "News classification skipped (LLM unavailable or malformed response)",
                extra={"symbol": symbol, "error": str(exc)},
            )


def _article_row_to_dict(row: NewsArticle) -> dict:
    return {
        "title": row.title,
        "summary": row.summary,
        "source": row.source,
        "url": row.url,
        "published_at": row.published_at.isoformat(),
        "thumbnail_url": row.thumbnail_url,
        "sentiment": row.sentiment,
        "impact_score": float(row.impact_score) if row.impact_score is not None else None,
        "related_tickers": row.related_tickers or [],
    }
