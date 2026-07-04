"""Initial schema — all tables + pgvector/pg_trgm extensions.

Revision ID: 0001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable required extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── channels ─────────────────────────────────────────────────────────
    op.create_table(
        "channels",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("platform", sa.Text(), nullable=False, server_default="youtube"),
        sa.Column("external_channel_id", sa.Text(), nullable=False),
        sa.Column("handle", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("subscriber_count", sa.BigInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("include_shorts", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("polling_interval_seconds", sa.Integer(), nullable=False, server_default="900"),
        sa.Column("last_polled_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_successful_poll_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_channels"),
        sa.UniqueConstraint("platform", "external_channel_id", name="uq_channels_platform_channel"),
    )
    op.create_index("idx_channels_active", "channels", ["is_active"], postgresql_where=sa.text("is_active = TRUE"))

    # ── videos ────────────────────────────────────────────────────────────
    op.create_table(
        "videos",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("external_video_id", sa.Text(), nullable=False),
        sa.Column("video_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("published_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=False, server_default="video"),
        sa.Column("live_status", sa.Text(), nullable=True),
        sa.Column("view_count", sa.BigInteger(), nullable=True),
        sa.Column("like_count", sa.BigInteger(), nullable=True),
        sa.Column("comment_count", sa.BigInteger(), nullable=True),
        sa.Column("pipeline_status", sa.Text(), nullable=False, server_default="DISCOVERED"),
        sa.Column("pipeline_failure_reason", sa.Text(), nullable=True),
        sa.Column("pipeline_retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pipeline_next_retry_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], name="fk_videos_channel_id_channels", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_videos"),
        sa.UniqueConstraint("channel_id", "external_video_id", name="uq_videos_channel_ext"),
    )
    op.create_index("idx_videos_pipeline_status", "videos", ["pipeline_status"])
    op.create_index("idx_videos_published_at", "videos", ["published_at"])
    op.create_index("idx_videos_channel", "videos", ["channel_id"])

    # ── video_stat_snapshots ──────────────────────────────────────────────
    op.create_table(
        "video_stat_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("captured_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("view_count", sa.BigInteger(), nullable=True),
        sa.Column("like_count", sa.BigInteger(), nullable=True),
        sa.Column("comment_count", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_video_stat_snapshots_video_id_videos", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_video_stat_snapshots"),
    )
    op.create_index("idx_stat_snapshots_video", "video_stat_snapshots", ["video_id", "captured_at"])

    # ── companies ─────────────────────────────────────────────────────────
    op.create_table(
        "companies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sector", sa.Text(), nullable=True),
        sa.Column("industry", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_companies"),
        sa.UniqueConstraint("name", name="uq_companies_name"),
    )

    # ── tickers ───────────────────────────────────────────────────────────
    op.create_table(
        "tickers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=True),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("exchange", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_tickers_company_id_companies", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_tickers"),
        sa.UniqueConstraint("symbol", "exchange", name="uq_tickers_symbol_exchange"),
    )

    # ── video_companies ───────────────────────────────────────────────────
    op.create_table(
        "video_companies",
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_video_companies_video_id_videos", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_video_companies_company_id_companies", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("video_id", "company_id", name="pk_video_companies"),
    )

    # ── topics / video_topics ─────────────────────────────────────────────
    op.create_table(
        "topics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_topics"),
        sa.UniqueConstraint("name", name="uq_topics_name"),
    )
    op.create_table(
        "video_topics",
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("topic_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_video_topics_video_id_videos", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], name="fk_video_topics_topic_id_topics", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("video_id", "topic_id", name="pk_video_topics"),
    )

    # ── transcripts ───────────────────────────────────────────────────────
    op.create_table(
        "transcripts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("generated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_transcripts_video_id_videos", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_transcripts"),
        sa.UniqueConstraint("video_id", name="uq_transcripts_video_id"),
    )
    op.execute("CREATE INDEX idx_transcripts_fulltext ON transcripts USING GIN (to_tsvector('english', full_text))")

    # ── transcript_segments ───────────────────────────────────────────────
    op.create_table(
        "transcript_segments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("transcript_id", sa.BigInteger(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("start_seconds", sa.Numeric(10, 2), nullable=False),
        sa.Column("end_seconds", sa.Numeric(10, 2), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"], name="fk_transcript_segments_transcript_id_transcripts", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_transcript_segments"),
        sa.UniqueConstraint("transcript_id", "sequence_no", name="uq_segments_transcript_seq"),
    )
    op.create_index("idx_segments_transcript", "transcript_segments", ["transcript_id"])

    # ── AI analysis tables ─────────────────────────────────────────────────
    op.create_table(
        "summaries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("executive_bullets", postgresql.JSONB(), nullable=False),
        sa.Column("detailed_summary", sa.Text(), nullable=False),
        sa.Column("model_used", sa.Text(), nullable=False),
        sa.Column("generated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_summaries_video_id_videos", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_summaries"),
        sa.UniqueConstraint("video_id", name="uq_summaries_video_id"),
    )
    op.create_table(
        "investment_theses",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("bull_case", sa.Text(), nullable=True),
        sa.Column("bear_case", sa.Text(), nullable=True),
        sa.Column("risks", sa.Text(), nullable=True),
        sa.Column("catalysts", sa.Text(), nullable=True),
        sa.Column("valuation_discussion", sa.Text(), nullable=True),
        sa.Column("economic_outlook", sa.Text(), nullable=True),
        sa.Column("market_outlook", sa.Text(), nullable=True),
        sa.Column("generated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_investment_theses_video_id_videos", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_investment_theses"),
        sa.UniqueConstraint("video_id", name="uq_investment_theses_video_id"),
    )
    op.create_table(
        "sentiments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("overall_sentiment", sa.Text(), nullable=False),
        sa.Column("bullish_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("bearish_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("neutral_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("generated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_sentiments_video_id_videos", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_sentiments"),
        sa.UniqueConstraint("video_id", name="uq_sentiments_video_id"),
        sa.CheckConstraint("(bullish_pct + bearish_pct + neutral_pct) BETWEEN 99 AND 101", name="ck_sentiments_pct_sum"),
    )

    op.create_table(
        "video_ticker_sentiments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("ticker_id", sa.BigInteger(), nullable=False),
        sa.Column("sentiment", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 2), nullable=True),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_video_ticker_sentiments_video_id_videos", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticker_id"], ["tickers.id"], name="fk_video_ticker_sentiments_ticker_id_tickers", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_video_ticker_sentiments"),
        sa.UniqueConstraint("video_id", "ticker_id", name="uq_video_ticker_sentiments"),
    )
    op.create_table(
        "quotes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("segment_id", sa.BigInteger(), nullable=True),
        sa.Column("quote_text", sa.Text(), nullable=False),
        sa.Column("speaker", sa.Text(), nullable=True),
        sa.Column("start_seconds", sa.Numeric(10, 2), nullable=True),
        sa.Column("importance_rank", sa.SmallInteger(), nullable=True),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_quotes_video_id_videos", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["segment_id"], ["transcript_segments.id"], name="fk_quotes_segment_id_transcript_segments", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_quotes"),
        sa.UniqueConstraint("video_id", "importance_rank", name="uq_quotes_video_rank"),
    )
    op.create_table(
        "key_numbers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("ticker_id", sa.BigInteger(), nullable=True),
        sa.Column("metric_type", sa.Text(), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=False),
        sa.Column("value_numeric", sa.Numeric(), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("start_seconds", sa.Numeric(10, 2), nullable=True),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_key_numbers_video_id_videos", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticker_id"], ["tickers.id"], name="fk_key_numbers_ticker_id_tickers", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_key_numbers"),
    )
    op.create_index("idx_key_numbers_video", "key_numbers", ["video_id"])
    op.create_index("idx_key_numbers_ticker", "key_numbers", ["ticker_id"])

    op.create_table(
        "actionable_insights",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("ticker_id", sa.BigInteger(), nullable=True),
        sa.Column("insight_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_actionable_insights_video_id_videos", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticker_id"], ["tickers.id"], name="fk_actionable_insights_ticker_id_tickers", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_actionable_insights"),
    )
    op.create_index("idx_insights_type", "actionable_insights", ["insight_type"])

    # ── embeddings (pgvector) ─────────────────────────────────────────────
    op.execute("CREATE TABLE embeddings (id BIGSERIAL PRIMARY KEY, transcript_segment_id BIGINT NOT NULL REFERENCES transcript_segments(id) ON DELETE CASCADE UNIQUE, video_id BIGINT NOT NULL REFERENCES videos(id) ON DELETE CASCADE, embedding VECTOR(1536) NOT NULL, model_used TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now())")
    op.execute("CREATE INDEX idx_embeddings_hnsw ON embeddings USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)")
    op.create_index("idx_embeddings_video", "embeddings", ["video_id"])

    # ── daily_reports ─────────────────────────────────────────────────────
    op.create_table(
        "daily_reports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("market_summary", sa.Text(), nullable=True),
        sa.Column("most_mentioned_stocks", postgresql.JSONB(), nullable=True),
        sa.Column("trending_sectors", postgresql.JSONB(), nullable=True),
        sa.Column("most_bullish_stocks", postgresql.JSONB(), nullable=True),
        sa.Column("most_bearish_stocks", postgresql.JSONB(), nullable=True),
        sa.Column("most_discussed_companies", postgresql.JSONB(), nullable=True),
        sa.Column("analyst_consensus", sa.Text(), nullable=True),
        sa.Column("conflicting_opinions", sa.Text(), nullable=True),
        sa.Column("interesting_insights", sa.Text(), nullable=True),
        sa.Column("generated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_daily_reports"),
        sa.UniqueConstraint("report_date", name="uq_daily_reports_report_date"),
    )
    op.create_table(
        "report_video_links",
        sa.Column("report_id", sa.BigInteger(), nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("link_type", sa.Text(), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=True),
        sa.ForeignKeyConstraint(["report_id"], ["daily_reports.id"], name="fk_report_video_links_report_id_daily_reports", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_report_video_links_video_id_videos", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("report_id", "video_id", "link_type", name="pk_report_video_links"),
    )

    # ── users / bookmarks / watchlists ─────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("hashed_password", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False, server_default="user"),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "bookmarks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_bookmarks_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_bookmarks_video_id_videos", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_bookmarks"),
        sa.UniqueConstraint("user_id", "video_id", name="uq_bookmarks_user_video"),
    )
    op.create_table(
        "watchlists",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False, server_default="Default"),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_watchlists_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_watchlists"),
        sa.UniqueConstraint("user_id", "name", name="uq_watchlists_user_name"),
    )
    op.create_table(
        "watchlist_items",
        sa.Column("watchlist_id", sa.BigInteger(), nullable=False),
        sa.Column("ticker_id", sa.BigInteger(), nullable=False),
        sa.Column("added_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["watchlist_id"], ["watchlists.id"], name="fk_watchlist_items_watchlist_id_watchlists", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticker_id"], ["tickers.id"], name="fk_watchlist_items_ticker_id_tickers", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("watchlist_id", "ticker_id", name="pk_watchlist_items"),
    )

    # ── task_logs ─────────────────────────────────────────────────────────
    op.create_table(
        "task_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("task_name", sa.Text(), nullable=False),
        sa.Column("video_id", sa.BigInteger(), nullable=True),
        sa.Column("channel_id", sa.BigInteger(), nullable=True),
        sa.Column("celery_task_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], name="fk_task_logs_video_id_videos", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], name="fk_task_logs_channel_id_channels", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_task_logs"),
    )
    op.create_index("idx_task_logs_video", "task_logs", ["video_id"])
    op.create_index("idx_task_logs_status", "task_logs", ["status", "task_name"])


def downgrade() -> None:
    # Drop all tables in reverse order
    op.drop_table("task_logs")
    op.drop_table("watchlist_items")
    op.drop_table("watchlists")
    op.drop_table("bookmarks")
    op.drop_table("users")
    op.drop_table("report_video_links")
    op.drop_table("daily_reports")
    op.execute("DROP TABLE IF EXISTS embeddings CASCADE")
    op.drop_table("actionable_insights")
    op.drop_table("key_numbers")
    op.drop_table("quotes")
    op.drop_table("video_ticker_sentiments")
    op.drop_table("sentiments")
    op.drop_table("investment_theses")
    op.drop_table("summaries")
    op.drop_table("transcript_segments")
    op.drop_table("transcripts")
    op.drop_table("video_topics")
    op.drop_table("topics")
    op.drop_table("video_companies")
    op.drop_table("tickers")
    op.drop_table("companies")
    op.drop_table("video_stat_snapshots")
    op.drop_table("videos")
    op.drop_table("channels")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS vector")
