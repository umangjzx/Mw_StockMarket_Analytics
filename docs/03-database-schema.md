# Database Schema

PostgreSQL 16+ with the `pgvector` and `pg_trgm` extensions. All tables use `BIGSERIAL`
surrogate keys, `created_at`/`updated_at` timestamps (UTC), and soft-delete is avoided in
favor of explicit status columns (simpler queries, no forgotten `WHERE deleted_at IS
NULL`).

## 1. Entity-Relationship Overview

```
channels 1───* videos 1───1 transcripts 1───* transcript_segments 1───* embeddings
                  │                                    │
                  │                                    └──* quotes
                  │
                  ├──1 summaries
                  ├──1 investment_theses
                  ├──1 sentiments
                  ├──* key_numbers
                  ├──* actionable_insights
                  ├──* video_companies *───1 companies 1───* tickers
                  ├──* video_topics *───1 topics
                  └──* video_stat_snapshots

daily_reports *───* videos   (via report_video_links, ranked "top videos"/"top quotes")

users 1───* watchlists 1───* watchlist_items *───1 tickers
users 1───* bookmarks *───1 videos

task_logs (independent — operational log of every Celery task execution)
```

## 2. Core Tables

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── Channels ─────────────────────────────────────────────────────────────
CREATE TABLE channels (
    id                  BIGSERIAL PRIMARY KEY,
    platform            TEXT NOT NULL DEFAULT 'youtube',     -- extensible: 'youtube','podcast_rss','twitter'
    external_channel_id TEXT NOT NULL,                        -- YouTube channel ID
    handle              TEXT,                                 -- e.g. '@CNBC'
    display_name        TEXT NOT NULL,
    description         TEXT,
    thumbnail_url       TEXT,
    country              TEXT,
    subscriber_count     BIGINT,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    include_shorts       BOOLEAN NOT NULL DEFAULT FALSE,
    polling_interval_seconds INTEGER NOT NULL DEFAULT 900,    -- 15 min default, configurable per channel
    last_polled_at       TIMESTAMPTZ,
    last_successful_poll_at TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (platform, external_channel_id)
);
CREATE INDEX idx_channels_active ON channels (is_active) WHERE is_active = TRUE;

-- ── Videos ───────────────────────────────────────────────────────────────
CREATE TABLE videos (
    id                  BIGSERIAL PRIMARY KEY,
    channel_id          BIGINT NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    external_video_id   TEXT NOT NULL,                        -- YouTube video ID
    video_url           TEXT NOT NULL,
    title               TEXT NOT NULL,
    description         TEXT,
    thumbnail_url       TEXT,
    published_at        TIMESTAMPTZ NOT NULL,
    duration_seconds    INTEGER,
    language             TEXT,
    tags                TEXT[],
    category             TEXT,
    content_type         TEXT NOT NULL DEFAULT 'video',       -- 'video','short','live','scheduled','podcast'
    live_status          TEXT,                                 -- 'none','upcoming','live','completed'
    -- denormalized latest stats (fast reads); history lives in video_stat_snapshots
    view_count            BIGINT,
    like_count             BIGINT,
    comment_count          BIGINT,
    pipeline_status       TEXT NOT NULL DEFAULT 'DISCOVERED',
        -- DISCOVERED, METADATA_SYNCED, TRANSCRIPT_PENDING, TRANSCRIPT_READY,
        -- ANALYSIS_PENDING, ANALYZED, EMBEDDING_PENDING, EMBEDDED, INDEXED, FAILED
    pipeline_failure_reason TEXT,
    pipeline_retry_count     INTEGER NOT NULL DEFAULT 0,
    pipeline_next_retry_at   TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (channel_id, external_video_id)
);
CREATE INDEX idx_videos_pipeline_status ON videos (pipeline_status);
CREATE INDEX idx_videos_published_at ON videos (published_at DESC);
CREATE INDEX idx_videos_channel ON videos (channel_id);

-- Historical view/like/comment counts (engagement trend over time, not just latest)
CREATE TABLE video_stat_snapshots (
    id            BIGSERIAL PRIMARY KEY,
    video_id      BIGINT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    captured_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    view_count    BIGINT,
    like_count    BIGINT,
    comment_count BIGINT
);
CREATE INDEX idx_stat_snapshots_video ON video_stat_snapshots (video_id, captured_at);

-- ── Transcripts ──────────────────────────────────────────────────────────
CREATE TABLE transcripts (
    id             BIGSERIAL PRIMARY KEY,
    video_id       BIGINT NOT NULL UNIQUE REFERENCES videos(id) ON DELETE CASCADE,
    source          TEXT NOT NULL,                 -- 'youtube_captions','whisper_local','whisper_api'
    language        TEXT,
    full_text       TEXT NOT NULL,
    word_count      INTEGER,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_transcripts_fulltext ON transcripts USING GIN (to_tsvector('english', full_text));

-- Timestamped chunks — the unit embeddings and RAG citations are built on
CREATE TABLE transcript_segments (
    id             BIGSERIAL PRIMARY KEY,
    transcript_id  BIGINT NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    sequence_no    INTEGER NOT NULL,
    start_seconds  NUMERIC(10,2) NOT NULL,
    end_seconds    NUMERIC(10,2) NOT NULL,
    text           TEXT NOT NULL,
    UNIQUE (transcript_id, sequence_no)
);
CREATE INDEX idx_segments_transcript ON transcript_segments (transcript_id);

-- ── Companies / Tickers / Topics (reference tables — defined early since
-- later analysis tables carry foreign keys to tickers) ────────────────────
CREATE TABLE companies (
    id            BIGSERIAL PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    sector        TEXT,
    industry      TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE tickers (
    id            BIGSERIAL PRIMARY KEY,
    company_id    BIGINT REFERENCES companies(id) ON DELETE SET NULL,
    symbol        TEXT NOT NULL,
    exchange      TEXT,                                -- 'NASDAQ','NYSE','NSE','BSE'
    UNIQUE (symbol, exchange)
);

CREATE TABLE video_companies (
    video_id    BIGINT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    company_id  BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    mention_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (video_id, company_id)
);

CREATE TABLE topics (
    id     BIGSERIAL PRIMARY KEY,
    name   TEXT NOT NULL UNIQUE                        -- 'AI','Semiconductors','Inflation','Interest Rates', ...
);

CREATE TABLE video_topics (
    video_id BIGINT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    topic_id BIGINT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    PRIMARY KEY (video_id, topic_id)
);

-- ── AI Analysis Output ───────────────────────────────────────────────────
CREATE TABLE summaries (
    id                  BIGSERIAL PRIMARY KEY,
    video_id            BIGINT NOT NULL UNIQUE REFERENCES videos(id) ON DELETE CASCADE,
    executive_bullets   JSONB NOT NULL,             -- ["...", "...", ...] (5 bullets)
    detailed_summary    TEXT NOT NULL,
    model_used          TEXT NOT NULL,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE investment_theses (
    id                   BIGSERIAL PRIMARY KEY,
    video_id             BIGINT NOT NULL UNIQUE REFERENCES videos(id) ON DELETE CASCADE,
    bull_case            TEXT,
    bear_case            TEXT,
    risks                TEXT,
    catalysts            TEXT,
    valuation_discussion TEXT,
    economic_outlook     TEXT,
    market_outlook       TEXT,
    generated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sentiments (
    id               BIGSERIAL PRIMARY KEY,
    video_id         BIGINT NOT NULL UNIQUE REFERENCES videos(id) ON DELETE CASCADE,
    overall_sentiment TEXT NOT NULL,                -- 'bullish','bearish','neutral','mixed'
    bullish_pct       NUMERIC(5,2) NOT NULL,
    bearish_pct       NUMERIC(5,2) NOT NULL,
    neutral_pct       NUMERIC(5,2) NOT NULL,
    confidence_score  NUMERIC(5,2) NOT NULL,
    generated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (bullish_pct + bearish_pct + neutral_pct BETWEEN 99 AND 101)
);

CREATE TABLE quotes (
    id           BIGSERIAL PRIMARY KEY,
    video_id     BIGINT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    quote_text   TEXT NOT NULL,
    speaker      TEXT,
    start_seconds NUMERIC(10,2),
    importance_rank SMALLINT,                        -- 1-10
    UNIQUE (video_id, importance_rank)
);

CREATE TABLE key_numbers (
    id            BIGSERIAL PRIMARY KEY,
    video_id      BIGINT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    ticker_id     BIGINT REFERENCES tickers(id),
    metric_type   TEXT NOT NULL,                     -- 'revenue','eps','growth_pct','margin','pe_ratio','market_cap','price_target','date','percentage'
    value_text    TEXT NOT NULL,                      -- raw as stated, e.g. "$61.2B"
    value_numeric NUMERIC,                             -- parsed, when possible
    context        TEXT,                               -- surrounding sentence for provenance
    start_seconds  NUMERIC(10,2)
);
CREATE INDEX idx_key_numbers_video ON key_numbers (video_id);
CREATE INDEX idx_key_numbers_ticker ON key_numbers (ticker_id);

CREATE TABLE actionable_insights (
    id            BIGSERIAL PRIMARY KEY,
    video_id      BIGINT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    insight_type  TEXT NOT NULL,   -- 'buy_idea','sell_idea','watchlist','risk','catalyst','earnings_date','macro_event'
    ticker_id     BIGINT REFERENCES tickers(id),
    description   TEXT NOT NULL,
    event_date    DATE
);
CREATE INDEX idx_insights_type ON actionable_insights (insight_type);

-- Per-ticker sentiment (a video can be bullish on NVDA and bearish on INTC at once)
CREATE TABLE video_ticker_sentiments (
    id           BIGSERIAL PRIMARY KEY,
    video_id     BIGINT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    ticker_id    BIGINT NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
    sentiment     TEXT NOT NULL,                     -- 'bullish','bearish','neutral'
    confidence_score NUMERIC(5,2),
    UNIQUE (video_id, ticker_id)
);

-- ── Embeddings (pgvector) ────────────────────────────────────────────────
CREATE TABLE embeddings (
    id                   BIGSERIAL PRIMARY KEY,
    transcript_segment_id BIGINT NOT NULL REFERENCES transcript_segments(id) ON DELETE CASCADE,
    video_id             BIGINT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,  -- denormalized for fast filtering
    embedding             VECTOR(1536) NOT NULL,        -- text-embedding-3-small
    model_used            TEXT NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (transcript_segment_id)
);
CREATE INDEX idx_embeddings_hnsw ON embeddings USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_embeddings_video ON embeddings (video_id);

-- ── Daily Reports ────────────────────────────────────────────────────────
CREATE TABLE daily_reports (
    id                     BIGSERIAL PRIMARY KEY,
    report_date            DATE NOT NULL UNIQUE,
    market_summary         TEXT,
    most_mentioned_stocks  JSONB,   -- [{ticker, mentions}, ...]
    trending_sectors        JSONB,
    most_bullish_stocks     JSONB,
    most_bearish_stocks     JSONB,
    most_discussed_companies JSONB,
    analyst_consensus        TEXT,
    conflicting_opinions      TEXT,
    interesting_insights      TEXT,
    generated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE report_video_links (
    report_id   BIGINT NOT NULL REFERENCES daily_reports(id) ON DELETE CASCADE,
    video_id    BIGINT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    link_type   TEXT NOT NULL,       -- 'top_video','top_quote_source'
    rank        SMALLINT,
    PRIMARY KEY (report_id, video_id, link_type)
);

-- ── Users, Bookmarks, Watchlists ─────────────────────────────────────────
CREATE TABLE users (
    id             BIGSERIAL PRIMARY KEY,
    email          TEXT NOT NULL UNIQUE,
    hashed_password TEXT,               -- nullable if SSO-only
    display_name    TEXT,
    role            TEXT NOT NULL DEFAULT 'user',   -- 'user','admin'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE bookmarks (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    video_id   BIGINT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    note       TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, video_id)
);

CREATE TABLE watchlists (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL DEFAULT 'Default',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, name)
);

CREATE TABLE watchlist_items (
    watchlist_id BIGINT NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    ticker_id    BIGINT NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
    added_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (watchlist_id, ticker_id)
);

-- ── Operational: task/job log (feeds admin + retry logic) ────────────────
CREATE TABLE task_logs (
    id             BIGSERIAL PRIMARY KEY,
    task_name      TEXT NOT NULL,
    video_id       BIGINT REFERENCES videos(id) ON DELETE SET NULL,
    channel_id     BIGINT REFERENCES channels(id) ON DELETE SET NULL,
    celery_task_id TEXT,
    status         TEXT NOT NULL,        -- 'started','succeeded','failed','retried'
    error_message  TEXT,
    duration_ms    INTEGER,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ
);
CREATE INDEX idx_task_logs_video ON task_logs (video_id);
CREATE INDEX idx_task_logs_status ON task_logs (status, task_name);
```

## 3. Design Notes

**Why split `summaries`, `investment_theses`, `sentiments` into separate tables instead of
one big `analysis` JSONB blob.** Each is generated by an independent LLM call and can fail
or be regenerated independently (e.g., re-running sentiment analysis with a better prompt
shouldn't touch the executive summary). Separate tables also make the `pipeline_status`
transitions and per-stage retry logic straightforward to query, and let API responses for
`/videos/{id}/summary` vs `/videos/{id}/thesis` be served without over-fetching.

**Why `key_numbers` and `quotes` are proper rows, not JSON arrays on `videos`.** They need
to be independently searchable/filterable (e.g., "show me every video mentioning a PE
ratio above X" or "quotes about the Fed this week") and joined to `tickers` — that only
works as first-class rows with foreign keys and indexes.

**Why `embeddings` references `transcript_segments`, not `videos` directly.** RAG needs
timestamp-level citations. Embedding at the video level would only support "this video is
relevant," not "here's the 45-second clip that answers your question."

**Why `video_ticker_sentiments` exists alongside the video-level `sentiments` table.** A
single video is rarely uniformly bullish or bearish — an analyst can be bullish on NVDA and
bearish on INTC in the same 20-minute video. Per-ticker sentiment is what "Bullish opinions
on AMD" search and the daily report's "most bullish/bearish stocks" sections are actually
built on; the video-level row is the overall tone.

**Why `video_stat_snapshots` exists alongside denormalized counts on `videos`.** Views/
likes/comments change after publish and trend data (view velocity) is itself a signal.
Snapshotting on every poll avoids losing that history while keeping the common case (latest
count) a single denormalized column read.
