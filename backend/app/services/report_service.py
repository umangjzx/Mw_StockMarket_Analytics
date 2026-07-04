"""
Daily report service.

Two-pass approach:
1. Structured aggregation queries (cheap, no LLM) — computes top tickers,
   sectors, sentiments, top videos/quotes for the trailing 24h.
2. One LLM synthesis pass over the top summaries to write narrative sections
   (analyst_consensus, conflicting_opinions, interesting_insights).
"""

import json
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.company import Company, Ticker, VideoCompany
from app.models.daily_report import DailyReport, ReportVideoLink
from app.models.quote import Quote
from app.models.sentiment import Sentiment, VideoTickerSentiment
from app.models.summary import Summary
from app.models.topic import Topic, VideoTopic
from app.models.video import Video
from app.providers.llm.base import LLMProvider

logger = get_logger(__name__)


class ReportService:

    def __init__(self, session: AsyncSession, llm: LLMProvider) -> None:
        self._session = session
        self._llm = llm

    async def generate(self, report_date: date | None = None) -> DailyReport:
        """
        Generate a daily report. If report_date is None, uses yesterday (UTC).
        Overwrites any existing report for that date.
        """
        if report_date is None:
            report_date = (datetime.now(UTC) - timedelta(days=1)).date()

        window_start = datetime.combine(report_date, datetime.min.time())
        window_end = window_start + timedelta(days=1)

        logger.info("Generating daily report", extra={"date": report_date.isoformat()})

        # ── 1. Structured aggregation ────────────────────────────────────────

        top_tickers   = await self._top_tickers(window_start, window_end)
        trending_secs = await self._trending_sectors(window_start, window_end)
        bullish_stocks = await self._most_sentiment_stocks(window_start, window_end, "bullish")
        bearish_stocks = await self._most_sentiment_stocks(window_start, window_end, "bearish")
        top_companies = await self._top_companies(window_start, window_end)
        top_videos    = await self._top_videos(window_start, window_end, limit=10)
        market_summary = await self._market_summary_text(window_start, window_end)

        # ── 2. LLM narrative synthesis ───────────────────────────────────────
        narrative = await self._synthesize_narrative(
            report_date, top_videos, top_tickers
        )

        # ── 3. Persist ───────────────────────────────────────────────────────
        # Delete existing report for this date
        from sqlalchemy import delete
        await self._session.execute(
            delete(DailyReport).where(DailyReport.report_date == report_date)
        )

        report = DailyReport(
            report_date=report_date,
            market_summary=market_summary,
            most_mentioned_stocks=top_tickers,
            trending_sectors=trending_secs,
            most_bullish_stocks=bullish_stocks,
            most_bearish_stocks=bearish_stocks,
            most_discussed_companies=top_companies,
            analyst_consensus=narrative.get("analyst_consensus"),
            conflicting_opinions=narrative.get("conflicting_opinions"),
            interesting_insights=narrative.get("interesting_insights"),
        )
        self._session.add(report)
        await self._session.flush()
        await self._session.refresh(report)

        # Link top videos
        for rank, video in enumerate(top_videos[:5], 1):
            self._session.add(ReportVideoLink(
                report_id=report.id,
                video_id=video["video_id"],
                link_type="top_video",
                rank=rank,
            ))

        await self._session.flush()
        logger.info("Daily report generated", extra={"date": report_date.isoformat(), "id": report.id})
        return report

    # ── Aggregation helpers ───────────────────────────────────────────────────

    async def _top_tickers(self, start: datetime, end: datetime) -> list[dict]:
        """Most-mentioned tickers in the window."""
        result = await self._session.execute(
            select(Ticker.symbol, func.sum(VideoCompany.mention_count).label("mentions"))
            .join(Company, Company.id == Ticker.company_id)
            .join(VideoCompany, VideoCompany.company_id == Company.id)
            .join(Video, Video.id == VideoCompany.video_id)
            .where(Video.published_at.between(start, end))
            .group_by(Ticker.symbol)
            .order_by(func.sum(VideoCompany.mention_count).desc())
            .limit(20)
        )
        return [{"ticker": row[0], "mentions": int(row[1])} for row in result.fetchall()]

    async def _trending_sectors(self, start: datetime, end: datetime) -> list[dict]:
        """Sectors ranked by video count."""
        result = await self._session.execute(
            select(Company.sector, func.count(VideoCompany.video_id).label("videos"))
            .join(VideoCompany, VideoCompany.company_id == Company.id)
            .join(Video, Video.id == VideoCompany.video_id)
            .where(Video.published_at.between(start, end))
            .where(Company.sector.isnot(None))
            .group_by(Company.sector)
            .order_by(func.count(VideoCompany.video_id).desc())
            .limit(10)
        )
        return [{"sector": row[0], "videos": int(row[1])} for row in result.fetchall()]

    async def _most_sentiment_stocks(
        self, start: datetime, end: datetime, sentiment: str, limit: int = 10
    ) -> list[dict]:
        """Tickers most-frequently bullish or bearish."""
        result = await self._session.execute(
            select(
                Ticker.symbol,
                func.count(VideoTickerSentiment.id).label("count"),
                func.avg(VideoTickerSentiment.confidence_score).label("avg_conf"),
            )
            .join(Ticker, Ticker.id == VideoTickerSentiment.ticker_id)
            .join(Video, Video.id == VideoTickerSentiment.video_id)
            .where(Video.published_at.between(start, end))
            .where(VideoTickerSentiment.sentiment == sentiment)
            .group_by(Ticker.symbol)
            .order_by(func.count(VideoTickerSentiment.id).desc())
            .limit(limit)
        )
        return [
            {"ticker": row[0], "count": int(row[1]), "avg_confidence": float(row[2] or 0)}
            for row in result.fetchall()
        ]

    async def _top_companies(self, start: datetime, end: datetime) -> list[dict]:
        result = await self._session.execute(
            select(Company.name, func.sum(VideoCompany.mention_count).label("mentions"))
            .join(VideoCompany, VideoCompany.company_id == Company.id)
            .join(Video, Video.id == VideoCompany.video_id)
            .where(Video.published_at.between(start, end))
            .group_by(Company.name)
            .order_by(func.sum(VideoCompany.mention_count).desc())
            .limit(15)
        )
        return [{"company": row[0], "mentions": int(row[1])} for row in result.fetchall()]

    async def _top_videos(self, start: datetime, end: datetime, limit: int = 10) -> list[dict]:
        """Top videos by view count (fallback: most recent)."""
        result = await self._session.execute(
            select(Video.id, Video.title, Video.view_count, Video.channel_id)
            .where(Video.published_at.between(start, end))
            .where(Video.pipeline_status == "INDEXED")
            .order_by(Video.view_count.desc().nullslast(), Video.published_at.desc())
            .limit(limit)
        )
        return [
            {"video_id": row[0], "title": row[1], "view_count": row[2], "channel_id": row[3]}
            for row in result.fetchall()
        ]

    async def _market_summary_text(self, start: datetime, end: datetime) -> str:
        """Auto-generated one-line market summary from aggregation."""
        video_count_r = await self._session.execute(
            select(func.count(Video.id))
            .where(Video.published_at.between(start, end))
            .where(Video.pipeline_status == "INDEXED")
        )
        video_count = video_count_r.scalar() or 0

        bull_r = await self._session.execute(
            select(func.count(Sentiment.id))
            .join(Video, Video.id == Sentiment.video_id)
            .where(Video.published_at.between(start, end))
            .where(Sentiment.overall_sentiment == "bullish")
        )
        bull_count = bull_r.scalar() or 0

        bear_r = await self._session.execute(
            select(func.count(Sentiment.id))
            .join(Video, Video.id == Sentiment.video_id)
            .where(Video.published_at.between(start, end))
            .where(Sentiment.overall_sentiment == "bearish")
        )
        bear_count = bear_r.scalar() or 0

        total_sent = bull_count + bear_count
        if total_sent == 0:
            tone = "neutral"
        elif bull_count / total_sent > 0.6:
            tone = "predominantly bullish"
        elif bear_count / total_sent > 0.6:
            tone = "predominantly bearish"
        else:
            tone = "mixed"

        return (
            f"{video_count} videos analyzed on {start.date().isoformat()}. "
            f"Overall market tone: {tone} "
            f"({bull_count} bullish, {bear_count} bearish)."
        )

    # ── LLM narrative synthesis ───────────────────────────────────────────────

    async def _synthesize_narrative(
        self, report_date: date, top_videos: list[dict], top_tickers: list[dict]
    ) -> dict:
        """One LLM pass over top summaries to write narrative sections."""
        if not top_videos:
            return {}

        # Pull summaries for top 5 videos
        video_ids = [v["video_id"] for v in top_videos[:5]]
        result = await self._session.execute(
            select(Summary.detailed_summary, Summary.video_id)
            .where(Summary.video_id.in_(video_ids))
        )
        summaries = result.fetchall()

        if not summaries:
            return {}

        context = "\n\n---\n\n".join(
            f"Video {row[1]}: {row[0][:800]}" for row in summaries
        )

        top_ticker_list = ", ".join(t["ticker"] for t in top_tickers[:10])

        system_prompt = """\
You are a financial market analyst writing a daily market digest. \
Based on the provided video summaries from today's financial media, write brief sections for:
1. analyst_consensus: The dominant analyst view today (2-3 sentences)
2. conflicting_opinions: Where analysts disagreed and why (2-3 sentences, or null)
3. interesting_insights: The most surprising or notable insight from today (2-3 sentences)

Respond with valid JSON only."""

        user_prompt = f"""\
Date: {report_date.isoformat()}
Top discussed tickers: {top_ticker_list}

TODAY'S TOP VIDEO SUMMARIES:
{context}

Return JSON:
{{
  "analyst_consensus": "...",
  "conflicting_opinions": "... or null",
  "interesting_insights": "..."
}}"""

        try:
            resp = await self._llm.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format="json_object",
                temperature=0.3,
            )
            import re, json as _json
            text = re.sub(r"```(?:json)?", "", resp.content).strip().rstrip("`").strip()
            return _json.loads(text)
        except Exception as exc:
            logger.warning("Narrative synthesis failed", extra={"error": str(exc)})
            return {}
