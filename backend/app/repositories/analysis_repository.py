"""
Analysis repository — read-only queries for all AI-generated content.
Writes are handled by AnalysisService directly.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.actionable_insight import ActionableInsight
from app.models.company import Company, Ticker, VideoCompany
from app.models.investment_thesis import InvestmentThesis
from app.models.key_number import KeyNumber
from app.models.quote import Quote
from app.models.sentiment import Sentiment, VideoTickerSentiment
from app.models.summary import Summary
from app.models.topic import Topic, VideoTopic


class AnalysisRepository:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_summary(self, video_id: int) -> Summary | None:
        result = await self._session.execute(
            select(Summary).where(Summary.video_id == video_id)
        )
        return result.scalar_one_or_none()

    async def get_thesis(self, video_id: int) -> InvestmentThesis | None:
        result = await self._session.execute(
            select(InvestmentThesis).where(InvestmentThesis.video_id == video_id)
        )
        return result.scalar_one_or_none()

    async def get_sentiment(self, video_id: int) -> Sentiment | None:
        result = await self._session.execute(
            select(Sentiment).where(Sentiment.video_id == video_id)
        )
        return result.scalar_one_or_none()

    async def get_ticker_sentiments(self, video_id: int) -> list[VideoTickerSentiment]:
        result = await self._session.execute(
            select(VideoTickerSentiment)
            .options(selectinload(VideoTickerSentiment.ticker))
            .where(VideoTickerSentiment.video_id == video_id)
        )
        return list(result.scalars().all())

    async def get_quotes(self, video_id: int) -> list[Quote]:
        result = await self._session.execute(
            select(Quote)
            .where(Quote.video_id == video_id)
            .order_by(Quote.importance_rank)
        )
        return list(result.scalars().all())

    async def get_key_numbers(self, video_id: int) -> list[KeyNumber]:
        result = await self._session.execute(
            select(KeyNumber)
            .options(selectinload(KeyNumber.ticker))
            .where(KeyNumber.video_id == video_id)
            .order_by(KeyNumber.id)
        )
        return list(result.scalars().all())

    async def get_insights(self, video_id: int) -> list[ActionableInsight]:
        result = await self._session.execute(
            select(ActionableInsight)
            .options(selectinload(ActionableInsight.ticker))
            .where(ActionableInsight.video_id == video_id)
            .order_by(ActionableInsight.id)
        )
        return list(result.scalars().all())

    async def get_video_companies(self, video_id: int) -> list[VideoCompany]:
        result = await self._session.execute(
            select(VideoCompany)
            .options(
                selectinload(VideoCompany.company).selectinload(Company.tickers)
            )
            .where(VideoCompany.video_id == video_id)
            .order_by(VideoCompany.mention_count.desc())
        )
        return list(result.scalars().all())

    async def get_video_ids_by_company(self, company_id: int) -> list[int]:
        """All video IDs that mention this company — the pivot used to scope
        the Company Intelligence module's AI video data and RAG chat."""
        result = await self._session.execute(
            select(VideoCompany.video_id).where(VideoCompany.company_id == company_id)
        )
        return [row[0] for row in result.fetchall()]

    async def get_topics(self, video_id: int) -> list[Topic]:
        result = await self._session.execute(
            select(Topic)
            .join(VideoTopic, VideoTopic.topic_id == Topic.id)
            .where(VideoTopic.video_id == video_id)
        )
        return list(result.scalars().all())
