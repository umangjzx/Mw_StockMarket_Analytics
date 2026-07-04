"""Aggregate all /api/v1 routers."""

from fastapi import APIRouter

from app.api.v1.routers import (
    admin,
    analysis,
    analytics,
    auth,
    channels,
    chat,
    company_intelligence,
    reports,
    scheduler,
    search,
    transcripts,
    videos,
    watchlist,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(channels.router)
api_router.include_router(videos.router)
api_router.include_router(transcripts.router)
api_router.include_router(analysis.router)
api_router.include_router(search.router)
api_router.include_router(chat.router)
api_router.include_router(company_intelligence.router)
api_router.include_router(reports.router)
api_router.include_router(analytics.router)
api_router.include_router(watchlist.router)
api_router.include_router(admin.router)
api_router.include_router(scheduler.router)
