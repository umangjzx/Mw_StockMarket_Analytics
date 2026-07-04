"""
Import all ORM models here so SQLAlchemy's mapper configuration is complete
before any session, migration, or relationship resolution happens.

Alembic's env.py also imports from this module.
"""

from app.models.channel import Channel
from app.models.video import Video
from app.models.video_stat_snapshot import VideoStatSnapshot
from app.models.transcript import Transcript, TranscriptSegment
from app.models.company import Company, Ticker, VideoCompany
from app.models.topic import Topic, VideoTopic
from app.models.summary import Summary
from app.models.investment_thesis import InvestmentThesis
from app.models.sentiment import Sentiment, VideoTickerSentiment
from app.models.quote import Quote
from app.models.key_number import KeyNumber
from app.models.actionable_insight import ActionableInsight
from app.models.embedding import Embedding
from app.models.daily_report import DailyReport, ReportVideoLink
from app.models.user import User, Bookmark, Watchlist, WatchlistItem
from app.models.task_log import TaskLog
from app.models.market_data import CompanyProfile, MarketQuote, PriceBar
from app.models.financials import FinancialStatement, Ratios, Earnings
from app.models.news_analyst import NewsArticle, AnalystSnapshot, ExecutiveSummary

__all__ = [
    "Channel",
    "Video",
    "VideoStatSnapshot",
    "Transcript",
    "TranscriptSegment",
    "Company",
    "Ticker",
    "VideoCompany",
    "Topic",
    "VideoTopic",
    "Summary",
    "InvestmentThesis",
    "Sentiment",
    "VideoTickerSentiment",
    "Quote",
    "KeyNumber",
    "ActionableInsight",
    "Embedding",
    "DailyReport",
    "ReportVideoLink",
    "User",
    "Bookmark",
    "Watchlist",
    "WatchlistItem",
    "TaskLog",
    "CompanyProfile",
    "MarketQuote",
    "PriceBar",
    "FinancialStatement",
    "Ratios",
    "Earnings",
    "NewsArticle",
    "AnalystSnapshot",
    "ExecutiveSummary",
]
