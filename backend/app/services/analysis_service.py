"""
Analysis service — runs a single LLM extractor for a video.

Each extractor is a separate async method that:
1. Builds a prompt
2. Calls the LLM provider
3. Parses the JSON response
4. Persists to the appropriate table

Each is independently callable and retryable — a failure in one extractor
does not block the others (they run in parallel via the Celery chord).
"""

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.actionable_insight import ActionableInsight
from app.models.company import Company, Ticker, VideoCompany
from app.models.investment_thesis import InvestmentThesis
from app.models.key_number import KeyNumber
from app.models.quote import Quote
from app.models.sentiment import Sentiment, VideoTickerSentiment
from app.models.summary import Summary
from app.models.topic import Topic, VideoTopic
from app.models.video import Video
from app.providers.llm.base import LLMProvider
from app.repositories.transcript_repository import TranscriptRepository
from app.repositories.video_repository import VideoRepository

logger = get_logger(__name__)

# Transcript length to pass to prompts — balance context vs cost
MAX_TRANSCRIPT_CHARS = 12_000


def _parse_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON, raising ValueError on failure."""
    text = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    return json.loads(text)


def _safe_decimal(value, default=None) -> Decimal | None:
    if value is None:
        return default
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError):
        return default


def _safe_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


# LLMs sometimes emit the literal word instead of JSON null when a field is
# unknown (e.g. "ticker": "NULL"). These are truthy strings, so plain
# `value or None` checks let them through as if they were real data.
_NULLISH_STRINGS = {"", "null", "none", "n/a", "na", "unknown", "nil", "undefined"}


def _clean_str(value) -> str | None:
    """Normalize an LLM-provided string, treating sentinel 'missing' values
    (None, empty, or words like "NULL"/"N/A") as genuinely absent."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text.lower() not in _NULLISH_STRINGS else None


def _clean_ticker(value) -> str | None:
    text = _clean_str(value)
    return text.upper() if text else None


class AnalysisService:
    """Runs individual LLM analysis extractors against a video's transcript."""

    def __init__(self, session: AsyncSession, llm: LLMProvider) -> None:
        self._session = session
        self._llm = llm
        self._video_repo = VideoRepository(session)
        self._transcript_repo = TranscriptRepository(session)

    async def _get_transcript_text(self, video_id: int) -> str:
        transcript = await self._transcript_repo.get_by_video_id(video_id)
        if not transcript:
            raise ValueError(f"No transcript found for video {video_id}")
        return transcript.full_text[:MAX_TRANSCRIPT_CHARS]

    async def _get_video(self, video_id: int) -> Video:
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        result = await self._session.execute(
            select(Video)
            .options(selectinload(Video.channel))
            .where(Video.id == video_id)
        )
        video = result.scalar_one_or_none()
        if not video:
            raise ValueError(f"Video {video_id} not found")
        return video

    # ── 1. Summary ────────────────────────────────────────────────────────────

    async def run_summary(self, video_id: int) -> dict:
        from app.prompts import executive_summary as p
        video = await self._get_video(video_id)
        transcript = await self._get_transcript_text(video_id)
        channel_name = video.channel.display_name if video.channel else "Unknown"

        response = await self._llm.complete(
            system_prompt=p.SYSTEM,
            user_prompt=p.build_user_prompt(transcript, video.title, channel_name),
            response_format="json_object",
        )
        data = _parse_json(response.content)

        # Upsert summary
        await self._session.execute(delete(Summary).where(Summary.video_id == video_id))
        summary = Summary(
            video_id=video_id,
            executive_bullets=data.get("executive_bullets", []),
            detailed_summary=data.get("detailed_summary", ""),
            model_used=response.model_used,
        )
        self._session.add(summary)
        await self._session.flush()
        logger.info("Summary saved", extra={"video_id": video_id})
        return {"extractor": "summary", "video_id": video_id, "ok": True}

    # ── 2. Investment thesis ──────────────────────────────────────────────────

    async def run_thesis(self, video_id: int) -> dict:
        from app.prompts import investment_thesis as p
        video = await self._get_video(video_id)
        transcript = await self._get_transcript_text(video_id)
        channel_name = video.channel.display_name if video.channel else "Unknown"

        response = await self._llm.complete(
            system_prompt=p.SYSTEM,
            user_prompt=p.build_user_prompt(transcript, video.title, channel_name),
            response_format="json_object",
        )
        data = _parse_json(response.content)

        await self._session.execute(
            delete(InvestmentThesis).where(InvestmentThesis.video_id == video_id)
        )
        thesis = InvestmentThesis(
            video_id=video_id,
            bull_case=data.get("bull_case"),
            bear_case=data.get("bear_case"),
            risks=data.get("risks"),
            catalysts=data.get("catalysts"),
            valuation_discussion=data.get("valuation_discussion"),
            economic_outlook=data.get("economic_outlook"),
            market_outlook=data.get("market_outlook"),
        )
        self._session.add(thesis)
        await self._session.flush()
        logger.info("Investment thesis saved", extra={"video_id": video_id})
        return {"extractor": "thesis", "video_id": video_id, "ok": True}

    # ── 3. Companies & tickers ────────────────────────────────────────────────

    async def run_entities(self, video_id: int) -> dict:
        from app.prompts import entity_extraction as p
        video = await self._get_video(video_id)
        transcript = await self._get_transcript_text(video_id)

        response = await self._llm.complete(
            system_prompt=p.SYSTEM,
            user_prompt=p.build_user_prompt(transcript, video.title),
            response_format="json_object",
        )
        data = _parse_json(response.content)
        entities = data.get("entities", [])

        # Remove existing associations for this video
        await self._session.execute(
            delete(VideoCompany).where(VideoCompany.video_id == video_id)
        )

        for ent in entities:
            company_name = _clean_str(ent.get("company_name"))
            if not company_name:
                continue
            # A ticker isn't always known (e.g. private companies, or the LLM
            # just doesn't recognize the symbol) — the company mention is
            # still worth recording, so only the ticker upsert is gated.
            ticker_symbol = _clean_ticker(ent.get("ticker"))

            # Upsert company
            result = await self._session.execute(
                select(Company).where(Company.name == company_name)
            )
            company = result.scalar_one_or_none()
            if not company:
                company = Company(
                    name=company_name,
                    sector=_clean_str(ent.get("sector")),
                )
                self._session.add(company)
                await self._session.flush()

            # Upsert ticker, if one was actually extracted
            if ticker_symbol:
                exchange = _clean_str(ent.get("exchange"))
                result = await self._session.execute(
                    select(Ticker).where(
                        Ticker.symbol == ticker_symbol,
                        Ticker.exchange == exchange,
                    )
                )
                ticker = result.scalar_one_or_none()
                if not ticker:
                    ticker = Ticker(
                        symbol=ticker_symbol,
                        exchange=exchange,
                        company_id=company.id,
                    )
                    self._session.add(ticker)
                    await self._session.flush()

            # Video–company junction
            vc = VideoCompany(
                video_id=video_id,
                company_id=company.id,
                mention_count=int(ent.get("mention_count", 1)),
            )
            self._session.add(vc)

        await self._session.flush()
        logger.info("Entities saved", extra={"video_id": video_id, "count": len(entities)})
        return {"extractor": "entities", "video_id": video_id, "ok": True, "count": len(entities)}

    # ── 4. Topics ─────────────────────────────────────────────────────────────

    async def run_topics(self, video_id: int) -> dict:
        from app.prompts import topics as p
        video = await self._get_video(video_id)
        transcript = await self._get_transcript_text(video_id)

        response = await self._llm.complete(
            system_prompt=p.SYSTEM,
            user_prompt=p.build_user_prompt(transcript, video.title),
            response_format="json_object",
        )
        data = _parse_json(response.content)
        topic_names: list[str] = data.get("topics", [])

        await self._session.execute(
            delete(VideoTopic).where(VideoTopic.video_id == video_id)
        )

        for name in topic_names:
            name = name.strip()
            if not name:
                continue
            result = await self._session.execute(select(Topic).where(Topic.name == name))
            topic = result.scalar_one_or_none()
            if not topic:
                topic = Topic(name=name)
                self._session.add(topic)
                await self._session.flush()

            self._session.add(VideoTopic(video_id=video_id, topic_id=topic.id))

        await self._session.flush()
        logger.info("Topics saved", extra={"video_id": video_id, "topics": topic_names})
        return {"extractor": "topics", "video_id": video_id, "ok": True, "topics": topic_names}

    # ── 5. Sentiment ─────────────────────────────────────────────────────────

    async def run_sentiment(self, video_id: int) -> dict:
        from app.prompts import sentiment as p

        video = await self._get_video(video_id)
        transcript = await self._get_transcript_text(video_id)

        # Collect tickers already extracted for this video (from entities run)
        ticker_result = await self._session.execute(
            select(Ticker.symbol)
            .join(VideoCompany, VideoCompany.company_id == Ticker.company_id)
            .where(VideoCompany.video_id == video_id)
        )
        tickers = [row[0] for row in ticker_result.fetchall()]

        response = await self._llm.complete(
            system_prompt=p.SYSTEM,
            user_prompt=p.build_user_prompt(transcript, video.title, tickers),
            response_format="json_object",
        )
        data = _parse_json(response.content)

        # Normalise percentages to sum to 100
        bull = float(data.get("bullish_pct", 0))
        bear = float(data.get("bearish_pct", 0))
        neut = float(data.get("neutral_pct", 0))
        total = bull + bear + neut
        if total > 0 and abs(total - 100) > 0.5:
            factor = 100 / total
            bull, bear, neut = bull * factor, bear * factor, neut * factor
        bull = round(bull, 2)
        bear = round(bear, 2)
        neut = round(100 - bull - bear, 2)  # Force sum to 100

        await self._session.execute(
            delete(Sentiment).where(Sentiment.video_id == video_id)
        )
        sentiment = Sentiment(
            video_id=video_id,
            overall_sentiment=data.get("overall_sentiment", "neutral"),
            bullish_pct=Decimal(str(bull)),
            bearish_pct=Decimal(str(bear)),
            neutral_pct=Decimal(str(neut)),
            confidence_score=_safe_decimal(data.get("confidence_score", 50)) or Decimal("50.00"),
        )
        self._session.add(sentiment)
        await self._session.flush()

        # Per-ticker sentiments
        await self._session.execute(
            delete(VideoTickerSentiment).where(VideoTickerSentiment.video_id == video_id)
        )
        for ts in data.get("ticker_sentiments", []):
            symbol = _clean_ticker(ts.get("ticker"))
            if not symbol:
                continue
            ticker_result = await self._session.execute(
                select(Ticker).where(Ticker.symbol == symbol)
            )
            ticker = ticker_result.scalar_one_or_none()
            if not ticker:
                continue
            self._session.add(VideoTickerSentiment(
                video_id=video_id,
                ticker_id=ticker.id,
                sentiment=ts.get("sentiment", "neutral"),
                confidence_score=_safe_decimal(ts.get("confidence_score")),
            ))

        await self._session.flush()
        logger.info("Sentiment saved", extra={"video_id": video_id, "overall": sentiment.overall_sentiment})
        return {"extractor": "sentiment", "video_id": video_id, "ok": True}

    # ── 6. Quotes ─────────────────────────────────────────────────────────────

    async def run_quotes(self, video_id: int) -> dict:
        from app.prompts import quotes as p
        video = await self._get_video(video_id)
        transcript = await self._get_transcript_text(video_id)
        channel_name = video.channel.display_name if video.channel else "Unknown"

        response = await self._llm.complete(
            system_prompt=p.SYSTEM,
            user_prompt=p.build_user_prompt(transcript, video.title, channel_name),
            response_format="json_object",
        )
        data = _parse_json(response.content)

        await self._session.execute(delete(Quote).where(Quote.video_id == video_id))

        for q in data.get("quotes", []):
            quote_text = (q.get("quote_text") or "").strip()
            if not quote_text:
                continue
            self._session.add(Quote(
                video_id=video_id,
                quote_text=quote_text[:1000],
                speaker=_clean_str(q.get("speaker")),
                start_seconds=_safe_decimal(q.get("start_seconds_hint")),
                importance_rank=q.get("importance_rank"),
            ))

        await self._session.flush()
        logger.info("Quotes saved", extra={"video_id": video_id, "count": len(data.get("quotes", []))})
        return {"extractor": "quotes", "video_id": video_id, "ok": True}

    # ── 7. Key numbers ────────────────────────────────────────────────────────

    async def run_key_numbers(self, video_id: int) -> dict:
        from app.prompts import key_numbers as p
        video = await self._get_video(video_id)
        transcript = await self._get_transcript_text(video_id)

        response = await self._llm.complete(
            system_prompt=p.SYSTEM,
            user_prompt=p.build_user_prompt(transcript, video.title),
            response_format="json_object",
        )
        data = _parse_json(response.content)

        await self._session.execute(delete(KeyNumber).where(KeyNumber.video_id == video_id))

        for kn in data.get("key_numbers", []):
            symbol = _clean_ticker(kn.get("ticker"))
            ticker_id = None
            if symbol:
                result = await self._session.execute(
                    select(Ticker).where(Ticker.symbol == symbol)
                )
                t = result.scalar_one_or_none()
                if t:
                    ticker_id = t.id

            self._session.add(KeyNumber(
                video_id=video_id,
                ticker_id=ticker_id,
                metric_type=kn.get("metric_type", "other"),
                value_text=(kn.get("value_text") or "")[:100],
                value_numeric=_safe_decimal(kn.get("value_numeric")),
                context=(kn.get("context") or "")[:300],
                start_seconds=_safe_decimal(kn.get("start_seconds_hint")),
            ))

        await self._session.flush()
        logger.info("Key numbers saved", extra={"video_id": video_id, "count": len(data.get("key_numbers", []))})
        return {"extractor": "key_numbers", "video_id": video_id, "ok": True}

    # ── 8. Actionable insights ────────────────────────────────────────────────

    async def run_insights(self, video_id: int) -> dict:
        from app.prompts import actionable_insights as p
        video = await self._get_video(video_id)
        transcript = await self._get_transcript_text(video_id)

        response = await self._llm.complete(
            system_prompt=p.SYSTEM,
            user_prompt=p.build_user_prompt(transcript, video.title),
            response_format="json_object",
        )
        data = _parse_json(response.content)

        await self._session.execute(
            delete(ActionableInsight).where(ActionableInsight.video_id == video_id)
        )

        for ins in data.get("insights", []):
            description = (ins.get("description") or "").strip()
            if not description:
                continue

            symbol = _clean_ticker(ins.get("ticker"))
            ticker_id = None
            if symbol:
                result = await self._session.execute(
                    select(Ticker).where(Ticker.symbol == symbol)
                )
                t = result.scalar_one_or_none()
                if t:
                    ticker_id = t.id

            self._session.add(ActionableInsight(
                video_id=video_id,
                ticker_id=ticker_id,
                insight_type=ins.get("insight_type", "watchlist"),
                description=description[:500],
                event_date=_safe_date(ins.get("event_date")),
            ))

        await self._session.flush()
        logger.info("Insights saved", extra={"video_id": video_id, "count": len(data.get("insights", []))})
        return {"extractor": "insights", "video_id": video_id, "ok": True}
