"""Analytics aggregation endpoints."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.company import Company, Ticker, VideoCompany
from app.models.sentiment import Sentiment, VideoTickerSentiment
from app.models.video import Video

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _window_start(window: str) -> datetime:
    # Return a naive UTC datetime to match how timestamps are stored in Postgres
    now = datetime.now(UTC).replace(tzinfo=None)
    hours = {"24h": 24, "7d": 24 * 7, "30d": 24 * 30}.get(window, 24)
    return now - timedelta(hours=hours)


@router.get("/trending-stocks")
async def trending_stocks(
    window: str = Query("24h", pattern="^(24h|7d|30d)$"),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Most-mentioned tickers over a rolling time window."""
    since = _window_start(window)
    result = await db.execute(
        select(Ticker.symbol, func.sum(VideoCompany.mention_count).label("mentions"))
        .join(Company, Company.id == Ticker.company_id)
        .join(VideoCompany, VideoCompany.company_id == Company.id)
        .join(Video, Video.id == VideoCompany.video_id)
        .where(Video.published_at >= since)
        .group_by(Ticker.symbol)
        .order_by(func.sum(VideoCompany.mention_count).desc())
        .limit(limit)
    )
    return {
        "window": window,
        "tickers": [{"ticker": r[0], "mentions": int(r[1])} for r in result.fetchall()],
    }


@router.get("/trending-sectors")
async def trending_sectors(
    window: str = Query("24h", pattern="^(24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Sector-level mention and sentiment aggregation."""
    since = _window_start(window)
    result = await db.execute(
        select(
            Company.sector,
            func.count(VideoCompany.video_id.distinct()).label("videos"),
            func.sum(VideoCompany.mention_count).label("mentions"),
        )
        .join(VideoCompany, VideoCompany.company_id == Company.id)
        .join(Video, Video.id == VideoCompany.video_id)
        .where(Video.published_at >= since)
        .where(Company.sector.isnot(None))
        .group_by(Company.sector)
        .order_by(func.count(VideoCompany.video_id.distinct()).desc())
    )
    return {
        "window": window,
        "sectors": [
            {"sector": r[0], "videos": int(r[1]), "mentions": int(r[2])}
            for r in result.fetchall()
        ],
    }


@router.get("/sentiment/{ticker}")
async def ticker_sentiment_series(
    ticker: str,
    window: str = Query("7d", pattern="^(24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Per-day sentiment time series for a ticker (for charting)."""
    since = _window_start(window)

    ticker_row = await db.execute(
        select(Ticker).where(Ticker.symbol == ticker.upper()).limit(1)
    )
    ticker_obj = ticker_row.scalar_one_or_none()
    if not ticker_obj:
        raise NotFoundError(f"Ticker {ticker} not found")

    result = await db.execute(
        select(
            func.date(Video.published_at).label("day"),
            func.count(VideoTickerSentiment.id).label("video_count"),
            func.avg(
                case(
                    (VideoTickerSentiment.sentiment == "bullish", 1.0),
                    else_=0.0
                )
            ).label("bullish_rate"),
            func.avg(
                case(
                    (VideoTickerSentiment.sentiment == "bearish", 1.0),
                    else_=0.0
                )
            ).label("bearish_rate"),
        )
        .join(Video, Video.id == VideoTickerSentiment.video_id)
        .where(VideoTickerSentiment.ticker_id == ticker_obj.id)
        .where(Video.published_at >= since)
        .group_by(func.date(Video.published_at))
        .order_by(func.date(Video.published_at))
    )
    rows = result.fetchall()
    return {
        "ticker": ticker.upper(),
        "window": window,
        "series": [
            {
                "date": str(r[0]),
                "video_count": int(r[1]),
                "bullish_pct": round(float(r[2] or 0) * 100, 1),
                "bearish_pct": round(float(r[3] or 0) * 100, 1),
                "neutral_pct": round((1 - float(r[2] or 0) - float(r[3] or 0)) * 100, 1),
            }
            for r in rows
        ],
    }


@router.get("/sector-heatmap")
async def sector_heatmap(
    window: str = Query("7d", pattern="^(24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Sector × sentiment matrix for the heatmap widget."""
    since = _window_start(window)
    result = await db.execute(
        select(
            Company.sector,
            Sentiment.overall_sentiment,
            func.count(Sentiment.id).label("count"),
        )
        .join(VideoCompany, VideoCompany.company_id == Company.id)
        .join(Video, Video.id == VideoCompany.video_id)
        .join(Sentiment, Sentiment.video_id == Video.id)
        .where(Video.published_at >= since)
        .where(Company.sector.isnot(None))
        .group_by(Company.sector, Sentiment.overall_sentiment)
    )
    # Build sector → {bullish, bearish, neutral, mixed} map
    heatmap: dict[str, dict] = {}
    for sector, sentiment, count in result.fetchall():
        if sector not in heatmap:
            heatmap[sector] = {"bullish": 0, "bearish": 0, "neutral": 0, "mixed": 0}
        heatmap[sector][sentiment] = int(count)

    return {"window": window, "heatmap": heatmap}


@router.get("/creator/{channel_id}")
async def creator_stats(
    channel_id: int,
    window: str = Query("30d", pattern="^(24h|7d|30d)$"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Per-creator stats: video volume, avg sentiment, top tickers covered."""
    since = _window_start(window)

    vcount = await db.execute(
        select(func.count(Video.id))
        .where(Video.channel_id == channel_id)
        .where(Video.published_at >= since)
    )
    video_count = vcount.scalar() or 0

    sent_r = await db.execute(
        select(
            func.avg(Sentiment.bullish_pct).label("avg_bull"),
            func.avg(Sentiment.bearish_pct).label("avg_bear"),
        )
        .join(Video, Video.id == Sentiment.video_id)
        .where(Video.channel_id == channel_id)
        .where(Video.published_at >= since)
    )
    sent_row = sent_r.fetchone()

    top_tickers_r = await db.execute(
        select(Ticker.symbol, func.sum(VideoCompany.mention_count).label("m"))
        .join(Company, Company.id == Ticker.company_id)
        .join(VideoCompany, VideoCompany.company_id == Company.id)
        .join(Video, Video.id == VideoCompany.video_id)
        .where(Video.channel_id == channel_id)
        .where(Video.published_at >= since)
        .group_by(Ticker.symbol)
        .order_by(func.sum(VideoCompany.mention_count).desc())
        .limit(10)
    )

    return {
        "channel_id": channel_id,
        "window": window,
        "video_count": video_count,
        "avg_bullish_pct": round(float(sent_row[0] or 0), 1) if sent_row else 0.0,
        "avg_bearish_pct": round(float(sent_row[1] or 0), 1) if sent_row else 0.0,
        "top_tickers": [r[0] for r in top_tickers_r.fetchall()],
    }
