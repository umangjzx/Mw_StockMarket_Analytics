"""
Watchlist and bookmarks endpoints.

This is a personal, single-user tool — no JWT/login flow. Every watchlist
and bookmark belongs to a single seeded user (see migration 0007). If this
ever needs real multi-user auth, reintroduce `Depends(get_current_user)`
from app.core.security and replace DEFAULT_USER_ID with the authenticated
user's id everywhere below.
"""

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import NotFoundError, AlreadyExistsError
from app.db.session import get_db
from app.models.company import Ticker
from app.models.user import Bookmark, Watchlist, WatchlistItem
from app.models.video import Video
from app.providers.market_data.composite_provider import build_market_data_provider
from app.services.company_intelligence_service import CompanyIntelligenceService

router = APIRouter(tags=["watchlist"])

DEFAULT_USER_ID = 1


class CreateWatchlistRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class AddTickerRequest(BaseModel):
    ticker: str = Field(..., min_length=1)


def _get_llm_provider():
    """Same pattern as search.py / company_intelligence.py."""
    if settings.LLM_PROVIDER == "ollama":
        from app.providers.llm.ollama_provider import OllamaProvider
        return OllamaProvider()
    from app.providers.llm.openai_provider import OpenAIProvider
    return OpenAIProvider()


# ── Watchlists ────────────────────────────────────────────────────────────────

@router.get("/watchlists")
async def list_watchlists(db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(
        select(Watchlist).where(Watchlist.user_id == DEFAULT_USER_ID)
    )
    lists = result.scalars().all()
    return {"watchlists": [{"id": w.id, "name": w.name, "created_at": w.created_at} for w in lists]}


@router.post("/watchlists", status_code=201)
async def create_watchlist(
    body: CreateWatchlistRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    existing = await db.execute(
        select(Watchlist).where(Watchlist.user_id == DEFAULT_USER_ID, Watchlist.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise AlreadyExistsError(f"Watchlist '{body.name}' already exists")
    wl = Watchlist(user_id=DEFAULT_USER_ID, name=body.name)
    db.add(wl)
    await db.flush()
    await db.refresh(wl)
    return {"id": wl.id, "name": wl.name, "created_at": wl.created_at}


@router.get("/watchlists/{watchlist_id}")
async def get_watchlist(
    watchlist_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Watchlist)
        .options(selectinload(Watchlist.items).selectinload(WatchlistItem.ticker))
        .where(Watchlist.id == watchlist_id, Watchlist.user_id == DEFAULT_USER_ID)
    )
    wl = result.scalar_one_or_none()
    if not wl:
        raise NotFoundError(f"Watchlist {watchlist_id} not found")

    items = [
        {"ticker_id": item.ticker_id, "symbol": item.ticker.symbol, "added_at": item.added_at}
        for item in wl.items
    ]
    return {"id": wl.id, "name": wl.name, "items": items}


@router.post("/watchlists/{watchlist_id}/items", status_code=201)
async def add_ticker_to_watchlist(
    watchlist_id: int,
    body: AddTickerRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    wl = await db.get(Watchlist, watchlist_id)
    if not wl or wl.user_id != DEFAULT_USER_ID:
        raise NotFoundError(f"Watchlist {watchlist_id} not found")

    ticker_r = await db.execute(
        select(Ticker).where(Ticker.symbol == body.ticker.upper()).limit(1)
    )
    ticker = ticker_r.scalar_one_or_none()
    if not ticker:
        # Not seen before — resolve it live the same way the Company
        # Intelligence page does, so tracking a brand-new ticker doesn't
        # require having viewed its page first (or ever mentioning it in a
        # video, despite what the old error message here used to say).
        llm = _get_llm_provider()
        service = CompanyIntelligenceService(
            session=db, market_provider=build_market_data_provider(), llm=llm, embedder=llm,
        )
        ticker = await service.resolve_ticker(body.ticker)

    existing = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.ticker_id == ticker.id,
        )
    )
    if existing.scalar_one_or_none():
        raise AlreadyExistsError(f"{body.ticker} already in watchlist")

    db.add(WatchlistItem(watchlist_id=watchlist_id, ticker_id=ticker.id))
    await db.flush()
    return {"status": "added", "ticker": ticker.symbol, "watchlist_id": watchlist_id}


@router.delete("/watchlists/{watchlist_id}/items/{ticker_id}", status_code=204)
async def remove_ticker_from_watchlist(
    watchlist_id: int,
    ticker_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    wl = await db.get(Watchlist, watchlist_id)
    if not wl or wl.user_id != DEFAULT_USER_ID:
        raise NotFoundError(f"Watchlist {watchlist_id} not found")

    item_r = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.ticker_id == ticker_id,
        )
    )
    item = item_r.scalar_one_or_none()
    if not item:
        raise NotFoundError(f"Ticker {ticker_id} not in watchlist {watchlist_id}")
    await db.delete(item)


@router.get("/watchlists/{watchlist_id}/feed")
async def watchlist_feed(
    watchlist_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Videos/insights relevant to tickers on this watchlist."""
    from sqlalchemy import func
    from app.models.company import VideoCompany

    wl_r = await db.execute(
        select(Watchlist)
        .options(selectinload(Watchlist.items))
        .where(Watchlist.id == watchlist_id, Watchlist.user_id == DEFAULT_USER_ID)
    )
    wl = wl_r.scalar_one_or_none()
    if not wl:
        raise NotFoundError(f"Watchlist {watchlist_id} not found")

    ticker_ids = [item.ticker_id for item in wl.items]
    if not ticker_ids:
        return {"watchlist_id": watchlist_id, "items": [], "total": 0}

    # Find company IDs for these tickers
    company_r = await db.execute(
        select(Ticker.company_id).where(Ticker.id.in_(ticker_ids)).where(Ticker.company_id.isnot(None))
    )
    company_ids = [r[0] for r in company_r.fetchall()]

    if not company_ids:
        return {"watchlist_id": watchlist_id, "items": [], "total": 0}

    count_r = await db.execute(
        select(func.count(Video.id.distinct()))
        .join(VideoCompany, VideoCompany.video_id == Video.id)
        .where(VideoCompany.company_id.in_(company_ids))
    )
    total = count_r.scalar() or 0

    videos_r = await db.execute(
        select(Video)
        .join(VideoCompany, VideoCompany.video_id == Video.id)
        .where(VideoCompany.company_id.in_(company_ids))
        .distinct()
        .order_by(Video.published_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    videos = videos_r.scalars().all()

    return {
        "watchlist_id": watchlist_id,
        "items": [
            {
                "id": v.id,
                "title": v.title,
                "published_at": v.published_at,
                "pipeline_status": v.pipeline_status,
                "thumbnail_url": v.thumbnail_url,
                "duration_seconds": v.duration_seconds,
            }
            for v in videos
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


# ── Bookmarks ─────────────────────────────────────────────────────────────────

@router.get("/bookmarks")
async def list_bookmarks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from sqlalchemy import func
    count_r = await db.execute(
        select(func.count(Bookmark.id)).where(Bookmark.user_id == DEFAULT_USER_ID)
    )
    total = count_r.scalar() or 0

    result = await db.execute(
        select(Bookmark)
        .options(selectinload(Bookmark.video))
        .where(Bookmark.user_id == DEFAULT_USER_ID)
        .order_by(Bookmark.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    bookmarks = result.scalars().all()
    return {
        "items": [
            {"id": b.id, "video_id": b.video_id, "note": b.note,
             "video_title": b.video.title if b.video else None, "created_at": b.created_at}
            for b in bookmarks
        ],
        "page": page, "page_size": page_size, "total": total,
    }


@router.post("/bookmarks", status_code=201)
async def add_bookmark(
    video_id: int = Query(...),
    note: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    video = await db.get(Video, video_id)
    if not video:
        raise NotFoundError(f"Video {video_id} not found")
    existing = await db.execute(
        select(Bookmark).where(Bookmark.user_id == DEFAULT_USER_ID, Bookmark.video_id == video_id)
    )
    if existing.scalar_one_or_none():
        raise AlreadyExistsError("Video already bookmarked")
    b = Bookmark(user_id=DEFAULT_USER_ID, video_id=video_id, note=note)
    db.add(b)
    await db.flush()
    await db.refresh(b)
    return {"id": b.id, "video_id": video_id, "note": note}


@router.delete("/bookmarks/{video_id}", status_code=204)
async def remove_bookmark(
    video_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Bookmark).where(Bookmark.user_id == DEFAULT_USER_ID, Bookmark.video_id == video_id)
    )
    b = result.scalar_one_or_none()
    if not b:
        raise NotFoundError(f"Bookmark for video {video_id} not found")
    await db.delete(b)
