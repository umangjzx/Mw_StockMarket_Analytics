"""
Company Intelligence service — the aggregator behind the module's main
endpoints. Composes:
  - MarketDataService for live quote / chart / profile data
  - AnalysisRepository for the existing per-video AI data, pivoted from a
    single video to "every video mentioning this company" via
    get_video_ids_by_company
  - EmbeddingRepository / RagChatService for ticker-scoped semantic search
    and RAG chat

AI-video-intelligence data is computed fresh on every request rather than
cached — trivially consistent with "recompute AI insights whenever new
videos are processed" without extra invalidation plumbing. Revisit with a
cache layer if request latency demands it once video volume grows.
"""

from app.core.exceptions import NotFoundError, ValidationError
from app.models.company import Ticker
from app.providers.llm.base import EmbeddingProvider, LLMProvider
from app.providers.market_data.base import MarketDataProvider, STATEMENT_PERIODS, STATEMENT_TYPES
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.embedding_repository import EmbeddingRepository
from app.repositories.market_data_repository import MarketDataRepository
from app.repositories.video_repository import VideoRepository
from app.services.analyst_service import AnalystService
from app.services.executive_summary_service import ExecutiveSummaryService
from app.services.financials_service import FinancialsService
from app.services.market_data_service import MarketDataService
from app.services.news_service import NewsService
from app.services.rag_chat_service import ChatAnswer, RagChatService
from app.services.technical_analysis_service import TechnicalAnalysisService


def _ticker_identity(ticker: Ticker) -> dict:
    return {
        "ticker_id": ticker.id,
        "symbol": ticker.symbol,
        "exchange": ticker.exchange,
        "company_id": ticker.company_id,
        "company_name": ticker.company.name if ticker.company else None,
        "sector": ticker.company.sector if ticker.company else None,
        "industry": ticker.company.industry if ticker.company else None,
    }


def _video_summary(video) -> dict:
    return {
        "id": video.id,
        "title": video.title,
        "external_video_id": video.external_video_id,
        "video_url": video.video_url,
        "published_at": video.published_at,
        "channel_name": video.channel.display_name if video.channel else None,
        "pipeline_status": video.pipeline_status,
    }


def _summary_dict(s) -> dict | None:
    if not s:
        return None
    return {"executive_bullets": s.executive_bullets, "detailed_summary": s.detailed_summary,
            "model_used": s.model_used, "generated_at": s.generated_at}


def _thesis_dict(t) -> dict | None:
    if not t:
        return None
    return {"bull_case": t.bull_case, "bear_case": t.bear_case, "risks": t.risks,
            "catalysts": t.catalysts, "valuation_discussion": t.valuation_discussion,
            "economic_outlook": t.economic_outlook, "market_outlook": t.market_outlook}


def _sentiment_dict(s) -> dict | None:
    if not s:
        return None
    return {"overall_sentiment": s.overall_sentiment, "bullish_pct": s.bullish_pct,
            "bearish_pct": s.bearish_pct, "neutral_pct": s.neutral_pct,
            "confidence_score": s.confidence_score}


def _key_number_dict(k) -> dict:
    return {"metric_type": k.metric_type, "value_text": k.value_text,
            "value_numeric": k.value_numeric, "context": k.context}


def _quote_dict(q) -> dict:
    return {"quote_text": q.quote_text, "speaker": q.speaker,
            "start_seconds": q.start_seconds, "importance_rank": q.importance_rank}


def _insight_dict(i) -> dict:
    return {"insight_type": i.insight_type, "description": i.description, "event_date": i.event_date}


# ── Executive summary context builders ──────────────────────────────────────
# Each turns one section's already-fetched dict into a short plain-text block
# for the LLM prompt. "unavailable" is stated plainly, per the prompt's rule
# against fabricating detail for missing sections.

def _summarize_quote(q: dict) -> str:
    if q.get("status") == "unavailable" or q.get("price") is None:
        return "Live quote unavailable."
    return (
        f"Price {q.get('price')} {q.get('currency', '')}, change {q.get('change_pct')}% today. "
        f"Day range {q.get('low')}-{q.get('high')}. 52-week range {q.get('week52_low')}-{q.get('week52_high')}. "
        f"Volume {q.get('volume')}. Market cap {q.get('market_cap')}."
    )


def _summarize_profile(p: dict) -> str:
    if p.get("status") == "unavailable" or not p.get("description"):
        return "Company profile unavailable."
    desc = (p.get("description") or "")[:600]
    return f"{desc} Headquarters: {p.get('headquarters')}. Employees: {p.get('employees')}."


def _summarize_ratios(r: dict) -> str:
    if r.get("status") == "unavailable":
        return "Ratios unavailable."
    return (
        f"P/E trailing {r.get('pe_trailing')} (forward {r.get('pe_forward')}), PEG {r.get('peg_ratio')}, "
        f"P/B {r.get('price_to_book')}, EV/EBITDA {r.get('ev_to_ebitda')}, ROE {r.get('roe')}, ROA {r.get('roa')}, "
        f"ROIC {r.get('roic')}, Debt/Equity {r.get('debt_to_equity')}, Dividend yield {r.get('dividend_yield')}, "
        f"Current ratio {r.get('current_ratio')}, Beta {r.get('beta')}."
    )


def _summarize_technicals(t: dict) -> str:
    if t.get("status") != "computed":
        return f"Technicals unavailable ({t.get('reason', 'insufficient data')})."
    macd = t.get("macd") or {}
    sma = t.get("sma") or {}
    return (
        f"Trend: {t.get('trend')}. RSI(14) {t.get('rsi_14')}, Stochastic RSI {t.get('stochastic_rsi_14')}. "
        f"MACD line {macd.get('macd_line')}, signal {macd.get('signal_line')}, histogram {macd.get('histogram')}. "
        f"SMA20/50/200: {sma.get('sma_20')}/{sma.get('sma_50')}/{sma.get('sma_200')}. "
        f"Support/resistance: {t.get('support_resistance')}."
    )


def _summarize_earnings(e: dict) -> str:
    if e.get("status") == "unavailable":
        return "Earnings data unavailable."
    parts = [f"Next earnings date: {e.get('next_earnings_date')}, EPS estimate avg {e.get('eps_estimate_avg')}."]
    if e.get("ai_summary"):
        parts.append(e["ai_summary"])
    return " ".join(parts)


def _summarize_news(n: dict) -> str:
    articles = n.get("articles") or []
    if not articles:
        return "No recent news available."
    lines = [
        f"- [{a.get('sentiment', 'unclassified')}] {a.get('title')} ({a.get('source')})"
        for a in articles[:8]
    ]
    return "\n".join(lines)


def _summarize_analyst(a: dict) -> str:
    if a.get("status") == "unavailable":
        return "Analyst data unavailable."
    return (
        f"Consensus: {a.get('recommendation_key')} (mean score {a.get('recommendation_mean')}, "
        f"{a.get('num_analyst_opinions')} analysts). Price target range "
        f"{a.get('target_low')}-{a.get('target_high')}, mean {a.get('target_mean')}. "
        f"Institutional ownership {a.get('held_pct_institutions')}, insider ownership {a.get('held_pct_insiders')}."
    )


def _summarize_video_intel(v: dict) -> str:
    videos = v.get("videos") or []
    if not videos:
        return "No YouTube commentary on this platform mentions this company yet."
    lines = [f"{len(videos)} analyzed video(s) mention this company."]
    for item in videos[:3]:
        sentiment = item.get("sentiment")
        thesis = item.get("thesis")
        if sentiment:
            lines.append(
                f"- \"{item['video']['title']}\": sentiment {sentiment.get('overall_sentiment')} "
                f"({sentiment.get('confidence_score')}% confidence)"
            )
        if thesis and thesis.get("bull_case"):
            lines.append(f"  Bull case: {thesis['bull_case'][:200]}")
        if thesis and thesis.get("bear_case"):
            lines.append(f"  Bear case: {thesis['bear_case'][:200]}")
    return "\n".join(lines)


class CompanyIntelligenceService:

    def __init__(
        self,
        session,
        market_provider: MarketDataProvider,
        llm: LLMProvider,
        embedder: EmbeddingProvider,
    ) -> None:
        self._session = session
        self._company_repo = CompanyRepository(session)
        self._analysis_repo = AnalysisRepository(session)
        self._video_repo = VideoRepository(session)
        self._market_provider = market_provider
        self._market_service = MarketDataService(session, market_provider)
        self._market_data_repo = MarketDataRepository(session)
        self._financials_service = FinancialsService(session, market_provider, llm)
        self._technicals_service = TechnicalAnalysisService(session)
        self._news_service = NewsService(session, market_provider, llm)
        self._analyst_service = AnalystService(session, market_provider)
        self._executive_summary_service = ExecutiveSummaryService(session, llm)
        self._llm = llm
        self._embedder = embedder

    # ── Resolution ───────────────────────────────────────────────────────────

    async def resolve_candidates(self, query: str) -> list[dict]:
        query = query.strip()
        if not query:
            return []

        local_ticker = await self._company_repo.get_ticker_by_symbol(query.upper())
        if local_ticker:
            return [_ticker_identity(local_ticker)]

        local_companies = await self._company_repo.search_companies_by_name(query, limit=5)
        local_matches = [
            _ticker_identity(t)
            for c in local_companies
            for t in c.tickers
        ]
        if local_matches:
            return local_matches

        provider_matches = await self._market_provider.search_symbol(query)
        return [
            {
                "ticker_id": None, "symbol": m.symbol, "exchange": m.exchange,
                "company_id": None, "company_name": m.name, "sector": None, "industry": None,
            }
            for m in provider_matches
        ]

    async def resolve_ticker(self, query: str) -> Ticker:
        query = query.strip()
        if not query:
            raise NotFoundError("Empty ticker/company query")

        local = await self._company_repo.get_ticker_by_symbol(query.upper())
        if local:
            return local

        local_companies = await self._company_repo.search_companies_by_name(query, limit=1)
        if local_companies and local_companies[0].tickers:
            return await self._company_repo.get_ticker_by_symbol(
                local_companies[0].tickers[0].symbol, local_companies[0].tickers[0].exchange
            )

        candidates = await self._market_provider.search_symbol(query)
        if not candidates:
            raise NotFoundError(f"Could not resolve '{query}' to a known ticker or company")

        ticker = await self._company_repo.get_or_create_by_resolved_symbol(candidates[0])
        await self._session.commit()
        return ticker

    # ── Sections ─────────────────────────────────────────────────────────────

    async def get_overview(self, query: str) -> dict:
        ticker = await self.resolve_ticker(query)
        quote = await self._market_service.get_quote(ticker.id, ticker.symbol, ticker.exchange)
        profile = (
            await self._market_service.get_profile(ticker.company_id, ticker.symbol, ticker.exchange)
            if ticker.company_id else {"status": "unavailable"}
        )
        video_ids = (
            await self._analysis_repo.get_video_ids_by_company(ticker.company_id)
            if ticker.company_id else []
        )
        return {
            "ticker": _ticker_identity(ticker),
            "quote": quote,
            "profile": profile,
            "video_mention_count": len(video_ids),
        }

    async def get_quote(self, query: str) -> dict:
        ticker = await self.resolve_ticker(query)
        quote = await self._market_service.get_quote(ticker.id, ticker.symbol, ticker.exchange)
        return {"ticker": _ticker_identity(ticker), "quote": quote}

    async def get_chart(self, query: str, chart_range: str) -> dict:
        ticker = await self.resolve_ticker(query)
        bars, status = await self._market_service.get_chart(
            ticker.id, ticker.symbol, ticker.exchange, chart_range
        )
        return {"ticker": _ticker_identity(ticker), "range": chart_range, "bars": bars, "status": status}

    async def get_profile(self, query: str) -> dict:
        ticker = await self.resolve_ticker(query)
        if not ticker.company_id:
            return {"ticker": _ticker_identity(ticker), "profile": {"status": "unavailable"}}
        profile = await self._market_service.get_profile(ticker.company_id, ticker.symbol, ticker.exchange)
        return {"ticker": _ticker_identity(ticker), "profile": profile}

    async def get_ratios(self, query: str) -> dict:
        ticker = await self.resolve_ticker(query)
        ratios = await self._financials_service.get_ratios(ticker.id, ticker.symbol, ticker.exchange)
        return {"ticker": _ticker_identity(ticker), "ratios": ratios}

    async def get_financials(self, query: str, statement_type: str, period_type: str) -> dict:
        if statement_type not in STATEMENT_TYPES:
            raise ValidationError(f"statement must be one of {STATEMENT_TYPES}, got {statement_type!r}")
        if period_type not in STATEMENT_PERIODS:
            raise ValidationError(f"period must be one of {STATEMENT_PERIODS}, got {period_type!r}")

        ticker = await self.resolve_ticker(query)
        if not ticker.company_id:
            return {
                "ticker": _ticker_identity(ticker), "statement_type": statement_type,
                "period_type": period_type, "periods": [], "status": "unavailable",
            }
        result = await self._financials_service.get_statements(
            ticker.company_id, ticker.symbol, ticker.exchange, statement_type, period_type
        )
        return {
            "ticker": _ticker_identity(ticker),
            "statement_type": statement_type,
            "period_type": period_type,
            **result,
        }

    async def get_earnings(self, query: str) -> dict:
        ticker = await self.resolve_ticker(query)
        if not ticker.company_id:
            return {"ticker": _ticker_identity(ticker), "earnings": {"status": "unavailable"}}
        earnings = await self._financials_service.get_earnings(ticker.company_id, ticker.symbol, ticker.exchange)
        return {"ticker": _ticker_identity(ticker), "earnings": earnings}

    async def get_technicals(self, query: str) -> dict:
        ticker = await self.resolve_ticker(query)
        # Technicals are computed from persisted daily bars — if none exist
        # yet (a ticker nobody's charted before), seed them the same way
        # get_chart()'s cold-start path does, so this endpoint works standalone.
        existing_bars = await self._market_data_repo.get_daily_bars(ticker.id)
        if not existing_bars:
            await self._market_service.get_chart(ticker.id, ticker.symbol, ticker.exchange, "1Y")
        technicals = await self._technicals_service.get_technicals(ticker.id)
        return {"ticker": _ticker_identity(ticker), "technicals": technicals}

    async def get_news(self, query: str, limit: int = 10) -> dict:
        ticker = await self.resolve_ticker(query)
        if not ticker.company_id:
            return {"ticker": _ticker_identity(ticker), "news": {"articles": [], "status": "unavailable"}}
        company_name = ticker.company.name if ticker.company else ticker.symbol
        news = await self._news_service.get_news(
            ticker.company_id, ticker.symbol, ticker.exchange, company_name, limit
        )
        return {"ticker": _ticker_identity(ticker), "news": news}

    async def get_analyst_insights(self, query: str) -> dict:
        ticker = await self.resolve_ticker(query)
        analyst = await self._analyst_service.get_analyst_insights(ticker.id, ticker.symbol, ticker.exchange)
        return {"ticker": _ticker_identity(ticker), "analyst": analyst}

    async def get_executive_summary(self, query: str) -> dict:
        """The capstone view — gathers every other section already built
        (quote, profile, ratios, technicals, earnings, news, analyst, and the
        platform's own AI video intelligence) into plain-text context blocks,
        then hands off to ExecutiveSummaryService for the actual synthesis."""
        ticker = await self.resolve_ticker(query)
        company_name = ticker.company.name if ticker.company else ticker.symbol

        overview = await self.get_overview(query)
        ratios = await self.get_ratios(query)
        technicals = await self.get_technicals(query)
        earnings = await self.get_earnings(query)
        news = await self.get_news(query, limit=8)
        analyst = await self.get_analyst_insights(query)
        video_intel = await self.get_intelligence(query)

        context = {
            "Live Quote": _summarize_quote(overview.get("quote", {})),
            "Company Profile": _summarize_profile(overview.get("profile", {})),
            "Key Ratios": _summarize_ratios(ratios.get("ratios", {})),
            "Technical Indicators": _summarize_technicals(technicals.get("technicals", {})),
            "Earnings": _summarize_earnings(earnings.get("earnings", {})),
            "Recent News": _summarize_news(news.get("news", {})),
            "Analyst Opinion": _summarize_analyst(analyst.get("analyst", {})),
            "Platform AI Video Analysis": _summarize_video_intel(video_intel),
        }

        result = await self._executive_summary_service.get_or_generate(
            ticker.id, ticker.symbol, company_name, context
        )
        return {"ticker": _ticker_identity(ticker), "executive_summary": result}

    async def get_videos(self, query: str) -> dict:
        ticker = await self.resolve_ticker(query)
        video_ids = (
            await self._analysis_repo.get_video_ids_by_company(ticker.company_id)
            if ticker.company_id else []
        )
        videos = await self._video_repo.get_by_ids(video_ids, pipeline_status="INDEXED")
        return {"ticker": _ticker_identity(ticker), "videos": [_video_summary(v) for v in videos]}

    async def get_intelligence(
        self, query: str, semantic_query: str | None = None, top_k: int = 10
    ) -> dict:
        ticker = await self.resolve_ticker(query)
        video_ids = (
            await self._analysis_repo.get_video_ids_by_company(ticker.company_id)
            if ticker.company_id else []
        )
        videos = await self._video_repo.get_by_ids(video_ids, pipeline_status="INDEXED")
        indexed_video_ids = [v.id for v in videos]

        bundle = []
        for video in videos:
            bundle.append({
                "video": _video_summary(video),
                "summary": _summary_dict(await self._analysis_repo.get_summary(video.id)),
                "thesis": _thesis_dict(await self._analysis_repo.get_thesis(video.id)),
                "sentiment": _sentiment_dict(await self._analysis_repo.get_sentiment(video.id)),
                "key_numbers": [_key_number_dict(k) for k in await self._analysis_repo.get_key_numbers(video.id)],
                "quotes": [_quote_dict(q) for q in await self._analysis_repo.get_quotes(video.id)],
                "insights": [_insight_dict(i) for i in await self._analysis_repo.get_insights(video.id)],
            })

        semantic_results: list[dict] = []
        if semantic_query and indexed_video_ids:
            # The AI-video bundle above is plain DB reads and has nothing to
            # do with the embedding provider — don't let a down/misconfigured
            # LLM provider (e.g. an expired Colab tunnel) take down data that
            # has no dependency on it. Degrade gracefully instead.
            try:
                embed_repo = EmbeddingRepository(self._session)
                vectors = await self._embedder.embed([semantic_query])
                semantic_results = await embed_repo.similarity_search(
                    query_vector=vectors[0], top_k=top_k, video_ids=indexed_video_ids
                )
            except Exception as exc:
                from app.core.logging import get_logger
                get_logger(__name__).warning(
                    "Semantic search unavailable, returning AI video bundle without it",
                    extra={"query": semantic_query, "error": str(exc)},
                )

        return {
            "ticker": _ticker_identity(ticker),
            "videos": bundle,
            "semantic_query": semantic_query,
            "semantic_results": semantic_results,
        }

    async def chat(self, query: str, question: str, top_k: int = 10) -> ChatAnswer:
        ticker = await self.resolve_ticker(query)
        video_ids = (
            await self._analysis_repo.get_video_ids_by_company(ticker.company_id)
            if ticker.company_id else []
        )
        if not video_ids:
            raise NotFoundError(
                f"No analyzed videos mention {ticker.symbol} yet — nothing to chat about"
            )

        rag = RagChatService(self._session, self._llm, self._embedder)
        return await rag.answer(question=question, top_k=top_k, video_ids=video_ids)
