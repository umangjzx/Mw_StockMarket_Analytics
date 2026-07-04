"""
Executive summary service — thin LLM synthesis + persistence layer. Deliberately
does NOT gather data itself: CompanyIntelligenceService (the orchestrator that
already holds every other section's data) builds the `context` dict of plain-text
summaries and passes it in here, keeping this service focused on the one thing
it owns — turning that context into a structured, cached executive briefing.
"""

import json
import re
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.news_analyst import ExecutiveSummary
from app.providers.llm.base import LLMProvider
from app.prompts import company_executive_summary as p
from app.repositories.executive_summary_repository import ExecutiveSummaryRepository

logger = get_logger(__name__)

_FRESHNESS = timedelta(hours=6)  # shorter than fundamentals — "why is it moving today" ages fast


def _now() -> datetime:
    return datetime.utcnow()


def _parse_json(raw: str) -> dict:
    text = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    return json.loads(text)


class ExecutiveSummaryService:

    def __init__(self, session: AsyncSession, llm: LLMProvider | None) -> None:
        self._session = session
        self._llm = llm
        self._repo = ExecutiveSummaryRepository(session)

    async def get_or_generate(
        self, ticker_id: int, symbol: str, company_name: str, context: dict[str, str]
    ) -> dict:
        existing = await self._repo.get(ticker_id)
        if existing and (_now() - existing.fetched_at) <= _FRESHNESS:
            return {**_row_to_dict(existing), "status": "cached"}

        if not self._llm:
            if existing:
                return {**_row_to_dict(existing), "status": "cached"}
            return {"status": "unavailable"}

        try:
            fields = await self._synthesize(symbol, company_name, context)
            row = await self._repo.upsert(ticker_id, fields, source="ollama", fetched_at=_now())
            await self._session.commit()
            return {**_row_to_dict(row), "status": "live"}
        except Exception as exc:
            logger.warning(
                "Executive summary synthesis failed, falling back",
                extra={"ticker_id": ticker_id, "symbol": symbol, "error": str(exc)},
            )
            if existing:
                return {**_row_to_dict(existing), "status": "cached"}
            return {"status": "unavailable"}

    async def _synthesize(self, symbol: str, company_name: str, context: dict[str, str]) -> dict:
        response = await self._llm.complete(
            system_prompt=p.SYSTEM,
            user_prompt=p.build_user_prompt(symbol, company_name, context),
            response_format="json_object",
            temperature=0.3,
        )
        data = _parse_json(response.content)
        return {
            "business_overview": data.get("business_overview", ""),
            "market_outlook": data.get("market_outlook", ""),
            "why_moving_today": data.get("why_moving_today", ""),
            "positive_factors": data.get("positive_factors", []) or [],
            "risks": data.get("risks", []) or [],
            "opportunities": data.get("opportunities", []) or [],
            "financial_health": data.get("financial_health", ""),
            "technical_outlook": data.get("technical_outlook", ""),
            "news_summary": data.get("news_summary", ""),
            "overall_sentiment": data.get("overall_sentiment", "neutral"),
            "investment_thesis": data.get("investment_thesis", ""),
            "short_term_outlook": data.get("short_term_outlook", ""),
            "long_term_outlook": data.get("long_term_outlook", ""),
            "confidence_score": float(data.get("confidence_score", 50) or 50),
        }


def _row_to_dict(row: ExecutiveSummary) -> dict:
    return {
        "business_overview": row.business_overview,
        "market_outlook": row.market_outlook,
        "why_moving_today": row.why_moving_today,
        "positive_factors": row.positive_factors or [],
        "risks": row.risks or [],
        "opportunities": row.opportunities or [],
        "financial_health": row.financial_health,
        "technical_outlook": row.technical_outlook,
        "news_summary": row.news_summary,
        "overall_sentiment": row.overall_sentiment,
        "investment_thesis": row.investment_thesis,
        "short_term_outlook": row.short_term_outlook,
        "long_term_outlook": row.long_term_outlook,
        "confidence_score": float(row.confidence_score),
        "source": row.source,
        "fetched_at": row.fetched_at.isoformat(),
    }
